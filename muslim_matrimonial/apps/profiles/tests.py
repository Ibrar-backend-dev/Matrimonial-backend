import io
from pathlib import Path
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


def make_upload(name, content, content_type="image/jpeg"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def make_image_bytes(image_format="JPEG", size=(4, 4)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(200, 50, 50)).save(buffer, format=image_format)
    return buffer.getvalue()


FAKE_PRESIGN_POST = {"url": "https://bucket.s3.amazonaws.com", "fields": {"key": "quarantine/x"}}


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
    """Covers the two-step presigned-upload flow: request a slot (mocking the
    S3 presign call), then finalize (mocking S3 object fetch/put/delete so the
    real Celery validation task -- Pillow decode, EXIF strip, re-encode --
    still runs against real image bytes, exercising real validation logic).
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

    def _request_upload(self, **payload):
        payload.setdefault("content_type", "image/jpeg")
        with patch("core.media_storage.create_presigned_post", return_value=FAKE_PRESIGN_POST):
            return self.client.post(self.request_url, payload, format="json")

    def _finalize(self, photo_id, data, content_type="image/jpeg"):
        finalize_url = reverse("profiles:photo-finalize", kwargs={"pk": photo_id})
        with (
            patch("core.media_storage.head_object", return_value={"size": len(data), "content_type": content_type}),
            patch("core.media_storage.get_object_bytes", return_value=data),
            patch("core.media_storage.put_object_bytes"),
            patch("core.media_storage.delete_object"),
            patch("core.media_storage.signed_delivery_url", return_value="https://cdn.example.com/signed"),
        ):
            return self.client.post(finalize_url)

    def test_valid_jpeg_accepted(self):
        response = self._request_upload(content_type="image/jpeg")
        self.assertEqual(response.status_code, 201)
        photo_id = response.data["photo"]["id"]
        finalize_response = self._finalize(photo_id, make_image_bytes("JPEG"))
        self.assertEqual(finalize_response.data["status"], "ready")
        self.assertEqual(Photo.objects.get(pk=photo_id).status, "ready")

    def test_valid_png_accepted(self):
        response = self._request_upload(content_type="image/png")
        photo_id = response.data["photo"]["id"]
        finalize_response = self._finalize(photo_id, make_image_bytes("PNG"))
        self.assertEqual(finalize_response.data["status"], "ready")

    def test_valid_webp_accepted(self):
        response = self._request_upload(content_type="image/webp")
        photo_id = response.data["photo"]["id"]
        finalize_response = self._finalize(photo_id, make_image_bytes("WEBP"))
        self.assertEqual(finalize_response.data["status"], "ready")

    def test_direct_file_upload_accepted(self):
        upload = make_upload("direct.jpg", make_image_bytes("JPEG"), content_type="image/jpeg")
        with patch("apps.profiles.views.validate_and_promote_photo.delay") as mock_delay:
            response = self.client.post(self.request_url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 201)
        photo_id = response.data["photo"]["id"]
        photo = Photo.objects.get(pk=photo_id)
        self.assertEqual(photo.status, "pending")
        mock_delay.assert_called_once_with(str(photo.pk))
        self.assertTrue((Path(settings.MEDIA_ROOT) / photo.storage_key).exists())

    def test_direct_file_upload_rejects_oversize(self):
        oversized = make_upload("large.jpg", make_image_bytes("JPEG") + b"\x00" * (3 * 1024 * 1024), content_type="image/jpeg")
        with patch("apps.profiles.views.validate_and_promote_photo.delay"):
            response = self.client.post(self.request_url, {"file": oversized}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_non_image_bytes_rejected(self):
        response = self._request_upload(content_type="image/jpeg")
        photo_id = response.data["photo"]["id"]
        finalize_response = self._finalize(photo_id, NOT_AN_IMAGE)
        self.assertEqual(finalize_response.data["status"], "failed")
        self.assertIsNone(Photo.objects.get(pk=photo_id).storage_key)

    def test_oversized_file_rejected(self):
        response = self._request_upload(content_type="image/jpeg")
        photo_id = response.data["photo"]["id"]
        oversized = make_image_bytes("JPEG") + b"\x00" * (3 * 1024 * 1024)
        finalize_response = self._finalize(photo_id, oversized)
        self.assertEqual(finalize_response.data["status"], "failed")

    def test_gallery_cap_of_six_enforced(self):
        with patch("core.media_storage.create_presigned_post", return_value=FAKE_PRESIGN_POST):
            for _ in range(6):
                response = self.client.post(self.request_url, {"content_type": "image/jpeg"}, format="json")
                self.assertEqual(response.status_code, 201)
            seventh = self.client.post(self.request_url, {"content_type": "image/jpeg"}, format="json")
        self.assertEqual(seventh.status_code, 400)
        self.assertEqual(Photo.objects.count(), 6)

    def test_is_primary_single_primary_enforced(self):
        with patch("core.media_storage.create_presigned_post", return_value=FAKE_PRESIGN_POST):
            self.client.post(self.request_url, {"content_type": "image/jpeg", "is_primary": True}, format="json")
            second = self.client.post(
                self.request_url, {"content_type": "image/jpeg", "is_primary": True}, format="json"
            )
        self.assertEqual(second.status_code, 201)
        photos = list(Photo.objects.filter(profile=self.profile))
        primaries = [p for p in photos if p.is_primary]
        self.assertEqual(len(primaries), 1)
