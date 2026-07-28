from django.urls import path

from .views import (
    GalleryAccessDetailView,
    GalleryAccessListView,
    OwnPhotoDetailView,
    OwnPhotoListCreateView,
    SharedGalleryView,
)

app_name = "gallery"

urlpatterns = [
    path("photos", OwnPhotoListCreateView.as_view(), name="photos"),
    path("photos/<uuid:pk>", OwnPhotoDetailView.as_view(), name="photo-detail"),
    path("users/<uuid:user_id>/photos", SharedGalleryView.as_view(), name="shared-photos"),
    path("access", GalleryAccessListView.as_view(), name="access-list"),
    path("access/<uuid:match_request_id>", GalleryAccessDetailView.as_view(), name="access-detail"),
]
