from django.core import mail
from django.test import override_settings
from django.core.cache import cache
from rest_framework.test import APITestCase

from .tasks import otp_cache_key, send_otp

# Tests run against a local in-memory cache rather than the Redis backend configured
# for production, mirroring how CELERY_TASK_ALWAYS_EAGER avoids needing a real broker.
TEST_CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES=TEST_CACHES,
)
class AuthenticationFlowTests(APITestCase):
    def setUp(self):
        cache.clear()

    def _register_and_verify(self, email="user@example.com", password="StrongPass123!"):
        credentials = {"email": email, "password": password}
        register = self.client.post("/api/auth/register", credentials, format="json")
        self.assertEqual(register.status_code, 201)
        otp = cache.get(otp_cache_key(email, "verify"))
        self.assertIsNotNone(otp)

        verify = self.client.post(
            "/api/auth/verify-otp",
            {"email": email, "otp": otp},
            format="json",
        )
        self.assertEqual(verify.status_code, 200)
        return credentials

    def test_register_sends_verification_email(self):
        mail.outbox = []
        self._register_and_verify()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("code", mail.outbox[0].body.lower())

    def test_register_verify_and_login(self):
        credentials = self._register_and_verify()

        login = self.client.post(
            "/api/auth/login",
            {"email": credentials["email"], "password": credentials["password"]},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("access", login.data)
        self.assertIn("refresh", login.data)

    def test_logout_blacklists_refresh_token(self):
        credentials = self._register_and_verify(email="logout@example.com")
        tokens = self.client.post("/api/auth/login", credentials, format="json").data

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        logout = self.client.post("/api/auth/logout", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(logout.status_code, 200)

        refresh_attempt = self.client.post("/api/auth/refresh-token", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refresh_attempt.status_code, 401)


@override_settings(CACHES=TEST_CACHES)
class SendOtpTaskTests(APITestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_stale_otp_is_not_emailed(self):
        mail.outbox = []
        email = "stale@example.com"
        cache.set(otp_cache_key(email, "verify"), "111111", 600)
        send_otp(email, "000000", "verify")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_current_otp_is_emailed(self):
        mail.outbox = []
        email = "current@example.com"
        cache.set(otp_cache_key(email, "verify"), "222222", 600)
        send_otp(email, "222222", "verify")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("222222", mail.outbox[0].body)
