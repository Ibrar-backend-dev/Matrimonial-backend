from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from apps.verifications.models import Verification


class VerificationAdminAPITest(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="password123",
            is_staff=True,
            role="admin",
            is_active=True,
            status="active",
        )
        self.user = User.objects.create_user(
            email="user@example.com",
            password="password123",
            is_active=True,
            status="active",
        )
        Verification.objects.create(user=self.user, doc_url="https://example.com/doc.jpg", visit_status="pending")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_pending_verification_list_pagination(self):
        url = reverse("pending-verifications")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_user_email(self):
        url = reverse("pending-verifications") + "?user_email=user@example.com"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["user_email"], "user@example.com")

    def test_admin_can_update_verification(self):
        verification = Verification.objects.get(user=self.user)
        url = reverse("verifications:admin-update", kwargs={"pk": verification.pk})
        response = self.client.patch(url, {"selfie_verified": True, "visit_status": "done"}, format="json")
        self.assertEqual(response.status_code, 200)
        verification.refresh_from_db()
        self.assertTrue(verification.selfie_verified)
        self.assertEqual(verification.visit_status, "done")
        self.assertEqual(verification.verified_by, self.admin)
