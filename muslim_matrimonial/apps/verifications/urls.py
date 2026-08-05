from django.urls import path

from .views import AdminVerificationUpdateView, PendingVerificationListView, VerificationSubmitView

app_name = "verifications"

urlpatterns = [
    path("submit", VerificationSubmitView.as_view(), name="submit"),
    path("admin/pending", PendingVerificationListView.as_view(), name="pending"),
    path("admin/<uuid:pk>", AdminVerificationUpdateView.as_view(), name="admin-update"),
]
