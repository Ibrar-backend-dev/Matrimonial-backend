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
from core.media_uploads import finalize_upload, reserve_upload_slot

from .models import GalleryAccess, PersonalPhoto
from .serializers import GalleryAccessSerializer, PersonalPhotoSerializer, PersonalPhotoUploadRequestSerializer
from .tasks import validate_and_promote_personal_photo


def other_match_user(match, user):
    return match.receiver if match.sender_id == user.id else match.sender


class OwnPhotoUploadRequestView(APIView):
    """Step 1 of the presigned-upload flow: reserve a quarantine slot and
    return a presigned POST the client uploads the file bytes to directly
    (B2/S3 never sees Django in the data path). See core/media_uploads.py
    and core/media_storage.py.
    """

    def post(self, request):
        serializer = PersonalPhotoUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        photo, post = reserve_upload_slot(
            model=PersonalPhoto,
            owner_field="user",
            owner=request.user,
            user=request.user,
            max_count=settings.MAX_PERSONAL_GALLERY_PHOTOS,
            key_prefix="personal_photos",
            content_type=data["content_type"],
        )
        photo.caption = data.get("caption", "")
        photo.display_order = data.get("display_order", 0)
        photo.save(update_fields=["caption", "display_order"])

        return Response(
            {
                "photo": PersonalPhotoSerializer(photo, context={"request": request}).data,
                "upload_url": post["url"],
                "upload_fields": post["fields"],
            },
            status=status.HTTP_201_CREATED,
        )


class OwnPhotoFinalizeView(APIView):
    """Step 2: confirm the S3 object exists and queue server-side validation."""

    def post(self, request, pk):
        photo = get_object_or_404(PersonalPhoto, pk=pk, user=request.user)
        finalize_upload(photo, validate_and_promote_personal_photo)
        return Response(PersonalPhotoSerializer(photo, context={"request": request}).data)


class OwnPhotoReissueUploadUrlView(APIView):
    """Mint a fresh presigned POST for a still-pending upload -- covers a
    client whose original URL expired or whose direct-to-B2 upload failed,
    without waiting for the 24h abandoned-upload sweep to clear the slot."""

    def post(self, request, pk):
        photo = get_object_or_404(PersonalPhoto, pk=pk, user=request.user)
        if photo.status != "pending":
            raise ValidationError("This upload has already been finalized.")
        post = media_storage.create_presigned_post(photo.storage_key, photo.content_type, settings.MEDIA_UPLOAD_MAX_BYTES)
        return Response({"upload_url": post["url"], "upload_fields": post["fields"]})


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
