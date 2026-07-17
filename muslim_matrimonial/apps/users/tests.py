from django.test import override_settings
from django.core.cache import cache
from rest_framework.test import APITestCase

from .tasks import otp_cache_key


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class AuthenticationFlowTests(APITestCase):
    def test_register_verify_and_login(self):
        credentials = {"phone": "+923001234567", "email": "user@example.com", "password": "StrongPass123!"}
        register = self.client.post("/api/auth/register", credentials, format="json")
        self.assertEqual(register.status_code, 201)
        otp = cache.get(otp_cache_key(credentials["phone"], "verify"))
        self.assertIsNotNone(otp)

        verify = self.client.post(
            "/api/auth/verify-otp",
            {"phone": credentials["phone"], "otp": otp},
            format="json",
        )
        self.assertEqual(verify.status_code, 200)

        login = self.client.post(
            "/api/auth/login",
            {"phone": credentials["phone"], "password": credentials["password"]},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("access", login.data)
        self.assertIn("refresh", login.data)
