from django.urls import path

from .views import PhotoUploadView, PreferenceView, PrivacySettingsView, ProfileCreateView, ProfileDetailView

app_name = "profiles"

urlpatterns = [
    path("", ProfileCreateView.as_view(), name="create"),
    path("upload-photo", PhotoUploadView.as_view(), name="upload-photo"),
    path("privacy-settings", PrivacySettingsView.as_view(), name="privacy-settings"),
    path("preferences", PreferenceView.as_view(), name="preferences"),
    path("<uuid:pk>", ProfileDetailView.as_view(), name="detail"),
]
