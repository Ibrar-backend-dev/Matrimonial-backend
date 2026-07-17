from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Preference, Profile
from .serializers import PhotoSerializer, PreferenceSerializer, ProfilePrivacySerializer, ProfileSerializer


class ProfileCreateView(generics.CreateAPIView):
    serializer_class = ProfileSerializer

    def perform_create(self, serializer):
        if Profile.objects.filter(user=self.request.user).exists():
            raise ValidationError("This user already has a profile.")
        serializer.save(user=self.request.user)


class ProfileDetailView(generics.RetrieveUpdateAPIView):
    queryset = Profile.objects.select_related("user").prefetch_related("photos")
    serializer_class = ProfileSerializer

    def get_object(self):
        profile = super().get_object()
        if self.request.method in {"PUT", "PATCH"}:
            if profile.user != self.request.user:
                raise PermissionDenied("Only the profile owner can update this profile.")
        elif profile.user != self.request.user and not self.request.user.is_staff:
            from apps.matches.services import is_profile_visible_to

            if not is_profile_visible_to(self.request.user, profile):
                raise NotFound("Profile not found.")
        return profile


class PhotoUploadView(generics.CreateAPIView):
    serializer_class = PhotoSerializer

    def perform_create(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)
        serializer.save(profile=profile)


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
