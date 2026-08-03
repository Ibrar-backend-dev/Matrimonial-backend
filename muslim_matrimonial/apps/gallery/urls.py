from django.urls import path

from .views import (
    GalleryAccessDetailView,
    GalleryAccessListView,
    OwnPhotoDetailView,
    OwnPhotoFinalizeView,
    OwnPhotoListView,
    OwnPhotoUploadRequestView,
    SharedGalleryView,
)

app_name = "gallery"

urlpatterns = [
    path("photos", OwnPhotoListView.as_view(), name="photos"),
    path("photos/upload", OwnPhotoUploadRequestView.as_view(), name="photo-upload-request"),
    path("photos/<uuid:pk>", OwnPhotoDetailView.as_view(), name="photo-detail"),
    path("photos/<uuid:pk>/finalize", OwnPhotoFinalizeView.as_view(), name="photo-finalize"),
    path("users/<uuid:user_id>/photos", SharedGalleryView.as_view(), name="shared-photos"),
    path("access", GalleryAccessListView.as_view(), name="access-list"),
    path("access/<uuid:match_request_id>", GalleryAccessDetailView.as_view(), name="access-detail"),
]
