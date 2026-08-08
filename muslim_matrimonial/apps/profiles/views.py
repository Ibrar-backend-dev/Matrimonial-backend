from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.media_uploads import finalize_upload, reserve_upload_slot
from core.permissions import IsAdminOrOwner
from core.throttles import AuthenticatedUserThrottle

from .models import Photo, Preference, Profile
from .serializers import PhotoSerializer, PhotoUploadRequestSerializer, PreferenceSerializer, ProfilePrivacySerializer, ProfileSerializer
from .tasks import validate_and_promote_photo


class ProfileCreateView(generics.CreateAPIView):
    serializer_class = ProfileSerializer

    def perform_create(self, serializer):
        if Profile.objects.filter(user=self.request.user).exists():
            raise ValidationError("This user already has a profile.")
        serializer.save(user=self.request.user)


class ProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Profile.objects.filter(is_deleted=False).select_related("user").prefetch_related("photos")
    serializer_class = ProfileSerializer
    permission_classes = [IsAdminOrOwner]
    throttle_classes = [AuthenticatedUserThrottle]
    throttle_scope = "profile"

    def get_object(self):
        # Retrieve the object from the queryset without invoking DRF's
        # automatic object-level permission check (super().get_object()
        # calls check_object_permissions). We need to decide visibility
        # first so incompatible profiles return 404 rather than 403.
        lookup = {self.lookup_field: self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)}
        profile = get_object_or_404(self.get_queryset(), **lookup)

        # For mutating requests, enforce object permissions.
        if self.request.method in {"PUT", "PATCH", "DELETE"}:
            self.check_object_permissions(self.request, profile)
        # For read requests from non-owners, apply visibility rules and
        # return 404 when a profile should be hidden.
        elif profile.user != self.request.user and not self.request.user.is_staff:
            from apps.matches.services import is_profile_visible_to

            if not is_profile_visible_to(self.request.user, profile):
                raise NotFound("Profile not found.")

        return profile

    def perform_destroy(self, instance):
        instance.soft_delete()


class PhotoUploadRequestView(APIView):
    """Step 1: reserve a gallery slot and return a presigned S3 POST.

    The client uploads the file bytes directly to S3 with the returned
    fields, then calls PhotoFinalizeView to trigger server-side validation.
    """

    throttle_classes = [AuthenticatedUserThrottle]
    throttle_scope = "profile"

    def post(self, request):
        profile = get_object_or_404(Profile, user=request.user, is_deleted=False)
        serializer = PhotoUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        photo, post = reserve_upload_slot(
            model=Photo,
            owner_field="profile",
            owner=profile,
            user=request.user,
            max_count=settings.MAX_PROFILE_GALLERY_PHOTOS,
            key_prefix="profile_photos",
            content_type=data["content_type"],
        )
        if data.get("is_primary") or data.get("privacy_level"):
            photo.is_primary = data.get("is_primary", False)
            photo.privacy_level = data.get("privacy_level")
            photo.save(update_fields=["is_primary", "privacy_level"])

        return Response(
            {
                "photo": PhotoSerializer(photo, context={"request": request}).data,
                "upload_url": post["url"],
                "upload_fields": post["fields"],
            },
            status=status.HTTP_201_CREATED,
        )


class PhotoFinalizeView(APIView):
    """Step 2: confirm the S3 object exists and queue server-side validation
    (file-signature check, decode, EXIF strip, re-encode, promote)."""

    throttle_classes = [AuthenticatedUserThrottle]
    throttle_scope = "profile"

    def post(self, request, pk):
        profile = get_object_or_404(Profile, user=request.user, is_deleted=False)
        photo = get_object_or_404(Photo, pk=pk, profile=profile)
        finalize_upload(photo, validate_and_promote_photo)
        return Response(PhotoSerializer(photo, context={"request": request}).data)


class PhotoListView(generics.ListAPIView):
    serializer_class = PhotoSerializer

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user, is_deleted=False)
        return profile.photos.exclude(status="failed").order_by("created_at")[:6]


class PhotoDeleteView(generics.DestroyAPIView):
    serializer_class = PhotoSerializer
    permission_classes = [IsAdminOrOwner]
    queryset = Photo.objects.all()
    throttle_classes = [AuthenticatedUserThrottle]
    throttle_scope = "profile"


class PrivacySettingsView(generics.GenericAPIView):
    serializer_class = ProfilePrivacySerializer

    def patch(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        serializer = ProfilePrivacySerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PreferenceView(generics.GenericAPIView):
    serializer_class = PreferenceSerializer

    def get(self, request):
        preference = get_object_or_404(Preference, user=request.user)
        return Response(PreferenceSerializer(preference).data)

    def put(self, request):
        preference = Preference.objects.filter(user=request.user).first()
        serializer = PreferenceSerializer(preference, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK if preference else status.HTTP_201_CREATED)

    def patch(self, request):
        preference = get_object_or_404(Preference, user=request.user)
        serializer = PreferenceSerializer(preference, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
