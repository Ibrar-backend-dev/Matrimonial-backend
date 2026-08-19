import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from .models import PersonalPhoto

User = get_user_model()

NOT_AN_IMAGE = b"This is definitely not an image, just plain text bytes." * 2
FAKE_PRESIGN_POST = {"url": "https://bucket.example/upload", "fields": {"key": "quarantine/fake"}}


def make_image_bytes(image_format="JPEG", size=(4, 4)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(200, 50, 50)).save(buffer, format=image_format)
    return buffer.getvalue()


class PersonalPhotoUploadFlowTests(TestCase):
    """Mirrors apps/profiles/tests.py::PhotoUploadFlowTests for the gallery's
    presigned-upload flow (request slot -> finalize). core.media_storage is
    fully mocked so this suite never touches the real bucket."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="gallery-uploader@example.com", password="StrongPass123!")
        self.client.force_authenticate(self.user)
        self.request_url = reverse("gallery:photo-upload-request")

        self.addCleanup(patch.stopall)
        patch("core.media_storage.create_presigned_post", return_value=FAKE_PRESIGN_POST).start()
        patch("core.media_storage.put_object_bytes").start()
        patch("core.media_storage.delete_object").start()

    def _request_upload(self, content_type="image/jpeg", **extra):
        return self.client.post(self.request_url, {"content_type": content_type, **extra}, format="json")

    def _finalize(self, photo_id, image_bytes):
        finalize_url = reverse("gallery:photo-finalize", args=[photo_id])
        with patch("core.media_storage.head_object", return_value={"size": len(image_bytes), "content_type": "image/jpeg"}), patch(
            "core.media_storage.get_object_bytes", return_value=image_bytes
        ):
            return self.client.post(finalize_url)

    def _upload_and_finalize(self, image_bytes, content_type="image/jpeg", **extra):
        requested = self._request_upload(content_type=content_type, **extra)
        photo_id = requested.data["photo"]["id"]
        return requested, self._finalize(photo_id, image_bytes)

    def test_upload_request_reserves_pending_photo_with_presign_fields(self):
        response = self._request_upload(content_type="image/jpeg", caption="Beach photo")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["photo"]["status"], "pending")
        self.assertEqual(response.data["photo"]["caption"], "Beach photo")
        self.assertEqual(response.data["upload_url"], FAKE_PRESIGN_POST["url"])
        self.assertEqual(response.data["upload_fields"], FAKE_PRESIGN_POST["fields"])

    def test_finalize_promotes_valid_jpeg(self):
        _, finalized = self._upload_and_finalize(make_image_bytes("JPEG"), content_type="image/jpeg")
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.data["status"], "ready")

    def test_finalize_rejects_non_image_bytes(self):
        _, finalized = self._upload_and_finalize(NOT_AN_IMAGE, content_type="image/jpeg")
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.data["status"], "failed")

    def test_finalize_twice_is_rejected(self):
        requested, finalized = self._upload_and_finalize(make_image_bytes("JPEG"), content_type="image/jpeg")
        self.assertEqual(finalized.status_code, 200)
        second = self._finalize(requested.data["photo"]["id"], make_image_bytes("JPEG"))
        self.assertEqual(second.status_code, 400)

    def test_max_gallery_photos_enforced(self):
        for _ in range(settings.MAX_PERSONAL_GALLERY_PHOTOS):
            response = self._request_upload(content_type="image/jpeg")
            self.assertEqual(response.status_code, 201)

        over_limit = self._request_upload(content_type="image/jpeg")
        self.assertEqual(over_limit.status_code, 400)
        self.assertEqual(PersonalPhoto.objects.filter(user=self.user).count(), settings.MAX_PERSONAL_GALLERY_PHOTOS)

    def test_reissue_upload_url_for_pending_photo(self):
        requested = self._request_upload(content_type="image/jpeg")
        photo_id = requested.data["photo"]["id"]
        reissue_url = reverse("gallery:photo-reissue-upload-url", args=[photo_id])

        fresh_presign = {"url": "https://bucket.example/upload-2", "fields": {"key": "quarantine/fake-2"}}
        with patch("core.media_storage.create_presigned_post", return_value=fresh_presign):
            response = self.client.post(reissue_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["upload_url"], fresh_presign["url"])
        self.assertEqual(response.data["upload_fields"], fresh_presign["fields"])

    def test_reissue_upload_url_rejected_once_finalized(self):
        requested, finalized = self._upload_and_finalize(make_image_bytes("JPEG"), content_type="image/jpeg")
        self.assertEqual(finalized.status_code, 200)
        reissue_url = reverse("gallery:photo-reissue-upload-url", args=[requested.data["photo"]["id"]])

        response = self.client.post(reissue_url)
        self.assertEqual(response.status_code, 400)
