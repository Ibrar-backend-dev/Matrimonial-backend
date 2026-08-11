from django.conf import settings
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.matches.models import MatchRequest
from apps.users.models import User
from core import media_storage
from core.media_uploads import finalize_upload  # reserve_upload_slot -- only needed by the presigned-upload mode below

from .models import GalleryAccess, PersonalPhoto
from .serializers import GalleryAccessSerializer, PersonalPhotoSerializer, PersonalPhotoUploadRequestSerializer
from .tasks import validate_and_promote_personal_photo


def other_match_user(match, user):
    return match.receiver if match.sender_id == user.id else match.sender


class OwnPhotoUploadRequestView(APIView):
    """Direct file upload, for local-dev/testing. The file is validated
    (2MB max, extension + signature check -- see PersonalPhotoUploadRequestSerializer)
    and written straight to quarantine storage; MEDIA_ROOT (project-root
    `media/` folder) is used automatically since no S3 bucket is configured
    locally. See core/media_storage.py.
    """

    def post(self, request):
        serializer = PersonalPhotoUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # --- Presigned S3 upload mode (disabled for now -- direct upload only) ---
        # if data.get("file"):
        #     ... (same direct-upload branch as below) ...
        #
        # photo, post = reserve_upload_slot(
        #     model=PersonalPhoto,
        #     owner_field="user",
        #     owner=request.user,
        #     user=request.user,
        #     max_count=settings.MAX_PERSONAL_GALLERY_PHOTOS,
        #     key_prefix="personal_photos",
        #     content_type=data["content_type"],
        # )
        # photo.caption = data.get("caption", "")
        # photo.display_order = data.get("display_order", 0)
        # photo.save(update_fields=["caption", "display_order"])
        #
        # return Response(
        #     {
        #         "photo": PersonalPhotoSerializer(photo, context={"request": request}).data,
        #         "upload_url": post["url"],
        #         "upload_fields": post["fields"],
        #     },
        #     status=status.HTTP_201_CREATED,
        # )

        if PersonalPhoto.objects.filter(user=request.user).exclude(status="failed").count() >= settings.MAX_PERSONAL_GALLERY_PHOTOS:
            raise ValidationError(f"A gallery may contain a maximum of {settings.MAX_PERSONAL_GALLERY_PHOTOS} photos.")

        file_obj = data["file"]
        file_obj.seek(0)
        content_type = file_obj.content_type
        storage_key = media_storage.quarantine_key("personal_photos", request.user.pk, content_type)
        photo = PersonalPhoto.objects.create(
            user=request.user,
            storage_key=storage_key,
            content_type=content_type,
            file=file_obj,
            caption=data.get("caption", ""),
            display_order=data.get("display_order", 0),
        )
        file_obj.seek(0)
        media_storage.put_object_bytes(storage_key, file_obj.read(), content_type)
        validate_and_promote_personal_photo.delay(str(photo.pk))
        return Response({"photo": PersonalPhotoSerializer(photo, context={"request": request}).data}, status=status.HTTP_201_CREATED)


class OwnPhotoFinalizeView(APIView):
    """Step 2: confirm the S3 object exists and queue server-side validation."""

    def post(self, request, pk):
        photo = get_object_or_404(PersonalPhoto, pk=pk, user=request.user)
        finalize_upload(photo, validate_and_promote_personal_photo)
        return Response(PersonalPhotoSerializer(photo, context={"request": request}).data)


class OwnPhotoListView(generics.ListAPIView):
    serializer_class = PersonalPhotoSerializer

    def get_queryset(self):
        return PersonalPhoto.objects.filter(user=self.request.user).exclude(status="failed")


class OwnPhotoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PersonalPhotoSerializer
    http_method_names = ("get", "patch", "delete", "head", "options")

    def get_queryset(self):
        return PersonalPhoto.objects.filter(user=self.request.user)


class SharedGalleryView(generics.ListAPIView):
    serializer_class = PersonalPhotoSerializer

    def get_queryset(self):
        owner = get_object_or_404(User, pk=self.kwargs["user_id"], is_active=True, status="active")
        viewer = self.request.user
        if viewer != owner and not viewer.is_staff:
            has_access = GalleryAccess.objects.filter(
                owner=owner,
                viewer=viewer,
                match_request__status="accepted",
            ).exists()
            if not has_access:
                raise Http404
        return PersonalPhoto.objects.filter(user=owner, status="ready")


class GalleryAccessListView(generics.GenericAPIView):
    serializer_class = GalleryAccessSerializer

    def get(self, request):
        matches = MatchRequest.objects.filter(
            Q(sender=request.user) | Q(receiver=request.user),
            status="accepted",
        ).select_related("sender", "receiver")
        granted_match_ids = set(
            GalleryAccess.objects.filter(owner=request.user).values_list("match_request_id", flat=True)
        )
        data = [
            {
                "match_request_id": match.id,
                "user_id": other_match_user(match, request.user).id,
                "has_access": match.id in granted_match_ids,
            }
            for match in matches
        ]
        return Response(self.get_serializer(data, many=True).data)


class GalleryAccessDetailView(generics.GenericAPIView):
    serializer_class = GalleryAccessSerializer

    @extend_schema(request=None, responses={200: GalleryAccessSerializer, 201: GalleryAccessSerializer})
    def post(self, request, match_request_id):
        match = get_object_or_404(
            MatchRequest.objects.select_related("sender", "receiver"),
            Q(sender=request.user) | Q(receiver=request.user),
            pk=match_request_id,
            status="accepted",
        )
        viewer = other_match_user(match, request.user)
        grant, created = GalleryAccess.objects.get_or_create(
            owner=request.user,
            match_request=match,
            defaults={"viewer": viewer},
        )
        data = self.get_serializer(
            {
                "match_request_id": match.id,
                "user_id": grant.viewer_id,
                "has_access": True,
            }
        ).data
        return Response(
            data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, match_request_id):
        match = get_object_or_404(
            MatchRequest,
            Q(sender=request.user) | Q(receiver=request.user),
            pk=match_request_id,
            status="accepted",
        )
        grant = get_object_or_404(GalleryAccess, owner=request.user, match_request=match)
        grant.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
