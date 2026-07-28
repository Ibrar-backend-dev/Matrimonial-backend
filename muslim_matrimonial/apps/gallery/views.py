from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.matches.models import MatchRequest
from apps.users.models import User

from .models import GalleryAccess, PersonalPhoto
from .serializers import GalleryAccessSerializer, PersonalPhotoSerializer


def other_match_user(match, user):
    return match.receiver if match.sender_id == user.id else match.sender


class OwnPhotoListCreateView(generics.ListCreateAPIView):
    serializer_class = PersonalPhotoSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        return PersonalPhoto.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            if PersonalPhoto.objects.filter(user=request.user).count() >= 6:
                raise ValidationError("A personal gallery can contain at most 6 photos.")
            photo = serializer.save(user=request.user)
        return Response(
            self.get_serializer(photo).data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(serializer.data),
        )


class OwnPhotoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PersonalPhotoSerializer
    parser_classes = (MultiPartParser, FormParser)
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
        return PersonalPhoto.objects.filter(user=owner)


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
