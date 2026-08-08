from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.verifications.views import PendingVerificationListView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.users.urls")),
    path("api/profile/", include("apps.profiles.urls")),
    path("api/verifications/", include("apps.verifications.urls")),
    path("api/matches/", include("apps.matches.urls")),
    path("api/chat/", include("apps.chat.urls")),
    # subscriptions, reviews and reports apps were removed from the project
    # their URL includes have been removed to avoid import errors
    path("api/gallery/", include("apps.gallery.urls")),
    path("api/admin/verifications/pending", PendingVerificationListView.as_view(), name="pending-verifications"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
