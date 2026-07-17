from django.urls import path

from .views import VerificationSubmitView

app_name = "verifications"

urlpatterns = [path("submit", VerificationSubmitView.as_view(), name="submit")]
