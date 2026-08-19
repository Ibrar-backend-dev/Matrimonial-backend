import io
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from core.validators import validate_image_file

from .models import Photo, Profile

User = get_user_model()

JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
WEBP_HEADER = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20
NOT_AN_IMAGE = b"This is definitely not an image, just plain text bytes." * 2

FAKE_PRESIGN_POST = {"url": "https://bucket.example/upload", "fields": {"key": "quarantine/fake"}}


def make_upload(name, content, content_type="image/jpeg"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def make_image_bytes(image_format="JPEG", size=(4, 4)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(200, 50, 50)).save(buffer, format=image_format)
    return buffer.getvalue()


class ValidateImageFileTests(TestCase):
    def test_accepts_jpeg_header(self):
        validate_image_file(make_upload("a.jpg", JPEG_HEADER))

    def test_accepts_png_header(self):
        validate_image_file(make_upload("a.png", PNG_HEADER))

    def test_accepts_webp_header(self):
        validate_image_file(make_upload("a.webp", WEBP_HEADER))

    def test_rejects_non_image_bytes(self):
        with self.assertRaises(DjangoValidationError):
            validate_image_file(make_upload("a.jpg", NOT_AN_IMAGE))

    def test_rejects_text_disguised_as_jpg_extension(self):
        upload = make_upload("fake.jpg", NOT_AN_IMAGE, content_type="image/jpeg")
        with self.assertRaises(DjangoValidationError):
            validate_image_file(upload)

    def test_seeks_back_to_start_after_reading_header(self):
        upload = make_upload("a.png", PNG_HEADER)
        validate_image_file(upload)
        self.assertEqual(upload.read(), PNG_HEADER)


class PhotoUploadFlowTests(TestCase):
    """Covers the presigned-upload flow: POST to upload-photo-request reserves
    a quarantine slot and returns a presigned POST (mocked here -- see
    PhotoUploadIntegrationTests for a real-B2 round trip); POST to
    /finalize then fetches the "uploaded" bytes and promotes/rejects the
    photo. core.media_storage is fully mocked so this suite never touches
    the real bucket.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="uploader@example.com", password="StrongPass123!")
        self.profile = Profile.objects.create(
            user=self.user,
            name="Test User",
            gender="male",
            dob="1995-01-01",
            city="City",
            country="Country",
            sect_maslak="sunni",
            education="BSc",
            marital_status="never_married",
        )
        self.client.force_authenticate(self.user)
        self.request_url = reverse("profiles:upload-photo-request")

        self.addCleanup(patch.stopall)
        patch("core.media_storage.create_presigned_post", return_value=FAKE_PRESIGN_POST).start()
        patch("core.media_storage.put_object_bytes").start()
        patch("core.media_storage.delete_object").start()

    def _request_upload(self, content_type="image/jpeg", **extra):
        return self.client.post(self.request_url, {"content_type": content_type, **extra}, format="json")

    def _finalize(self, photo_id, image_bytes):
        finalize_url = reverse("profiles:photo-finalize", args=[photo_id])
        with patch("core.media_storage.head_object", return_value={"size": len(image_bytes), "content_type": "image/jpeg"}), patch(
            "core.media_storage.get_object_bytes", return_value=image_bytes
        ):
            return self.client.post(finalize_url)

    def _upload_and_finalize(self, image_bytes, content_type="image/jpeg"):
        requested = self._request_upload(content_type=content_type)
        photo_id = requested.data["photo"]["id"]
        return requested, self._finalize(photo_id, image_bytes)

    def test_upload_request_reserves_pending_photo_with_presign_fields(self):
        response = self._request_upload(content_type="image/jpeg")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["photo"]["status"], "pending")
        self.assertEqual(response.data["upload_url"], FAKE_PRESIGN_POST["url"])
        self.assertEqual(response.data["upload_fields"], FAKE_PRESIGN_POST["fields"])
        photo_id = response.data["photo"]["id"]
        self.assertEqual(Photo.objects.get(pk=photo_id).status, "pending")

    def test_finalize_promotes_valid_jpeg(self):
        _, finalized = self._upload_and_finalize(make_image_bytes("JPEG"), content_type="image/jpeg")
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.data["status"], "ready")

    def test_finalize_promotes_valid_png(self):
        _, finalized = self._upload_and_finalize(make_image_bytes("PNG"), content_type="image/png")
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.data["status"], "ready")

    def test_finalize_promotes_valid_webp(self):
        _, finalized = self._upload_and_finalize(make_image_bytes("WEBP"), content_type="image/webp")
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.data["status"], "ready")

    def test_finalize_rejects_non_image_bytes(self):
        _, finalized = self._upload_and_finalize(NOT_AN_IMAGE, content_type="image/jpeg")
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.data["status"], "failed")

    def test_finalize_rejects_oversized_image(self):
        oversized = make_image_bytes("JPEG") + b"\x00" * (settings.MEDIA_UPLOAD_MAX_BYTES + 1024)
        _, finalized = self._upload_and_finalize(oversized, content_type="image/jpeg")
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.data["status"], "failed")

    def test_finalize_twice_is_rejected(self):
        requested, finalized = self._upload_and_finalize(make_image_bytes("JPEG"), content_type="image/jpeg")
        self.assertEqual(finalized.status_code, 200)
        photo_id = requested.data["photo"]["id"]
        second = self._finalize(photo_id, make_image_bytes("JPEG"))
        self.assertEqual(second.status_code, 400)

    def test_model_rejects_invalid_file_on_save(self):
        with self.assertRaises(DjangoValidationError):
            Photo.objects.create(
                profile=self.profile,
                file=SimpleUploadedFile("bad.jpg", NOT_AN_IMAGE, content_type="image/jpeg"),
            )

    def test_uploading_new_photo_replaces_previous(self):
        first = self._request_upload(content_type="image/jpeg")
        self.assertEqual(first.status_code, 201)
        first_id = first.data["photo"]["id"]

        with patch("apps.profiles.models.delete_photo_object") as mock_delete_task:
            second = self._request_upload(content_type="image/jpeg")

        self.assertEqual(second.status_code, 201)
        self.assertEqual(Photo.objects.filter(profile=self.profile).count(), 1)
        self.assertFalse(Photo.objects.filter(pk=first_id).exists())
        remaining = Photo.objects.get(profile=self.profile)
        self.assertNotEqual(remaining.pk, first_id)
        mock_delete_task.delay.assert_called_once()

    def test_reissue_upload_url_for_pending_photo(self):
        requested = self._request_upload(content_type="image/jpeg")
        photo_id = requested.data["photo"]["id"]
        reissue_url = reverse("profiles:photo-reissue-upload-url", args=[photo_id])

        fresh_presign = {"url": "https://bucket.example/upload-2", "fields": {"key": "quarantine/fake-2"}}
        with patch("core.media_storage.create_presigned_post", return_value=fresh_presign):
            response = self.client.post(reissue_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["upload_url"], fresh_presign["url"])
        self.assertEqual(response.data["upload_fields"], fresh_presign["fields"])

    def test_reissue_upload_url_rejected_once_finalized(self):
        requested, finalized = self._upload_and_finalize(make_image_bytes("JPEG"), content_type="image/jpeg")
        self.assertEqual(finalized.status_code, 200)
        reissue_url = reverse("profiles:photo-reissue-upload-url", args=[requested.data["photo"]["id"]])

        response = self.client.post(reissue_url)
        self.assertEqual(response.status_code, 400)


class PhotoUploadIntegrationTests(TestCase):
    """Real round trip against the live B2 bucket configured in .env: presign
    -> direct-to-B2 upload -> finalize. Skipped by default so the ordinary
    `pytest` run never depends on live network access; opt in explicitly
    with RUN_B2_INTEGRATION_TESTS=1 (and real bucket credentials in .env).
    """

    @classmethod
    def setUpClass(cls):
        import os

        if not os.environ.get("RUN_B2_INTEGRATION_TESTS"):
            raise __import__("unittest").SkipTest("Set RUN_B2_INTEGRATION_TESTS=1 to run the live-B2 integration test.")
        super().setUpClass()

    def test_full_presign_upload_finalize_round_trip(self):
        import requests

        client = APIClient()
        user = User.objects.create_user(email="integration@example.com", password="StrongPass123!")
        Profile.objects.create(
            user=user,
            name="Integration User",
            gender="male",
            dob="1995-01-01",
            city="City",
            country="Country",
            sect_maslak="sunni",
            education="BSc",
            marital_status="never_married",
        )
        client.force_authenticate(user)

        requested = client.post(reverse("profiles:upload-photo-request"), {"content_type": "image/jpeg"}, format="json")
        self.assertEqual(requested.status_code, 201)
        image_bytes = make_image_bytes("JPEG")
        upload_response = requests.post(
            requested.data["upload_url"],
            data=requested.data["upload_fields"],
            files={"file": ("photo.jpg", image_bytes, "image/jpeg")},
        )
        self.assertIn(upload_response.status_code, (200, 204))

        finalize_url = reverse("profiles:photo-finalize", args=[requested.data["photo"]["id"]])
        finalized = client.post(finalize_url)
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.data["status"], "ready")
