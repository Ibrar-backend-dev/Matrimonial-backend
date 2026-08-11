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


# FAKE_PRESIGN_POST = {"url": "https://bucket.s3.amazonaws.com", "fields": {"key": "quarantine/x"}}  -- presigned mode disabled for now


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
    """Covers the direct-upload flow (local-dev/testing): the file is
    validated up front (core/validators.py:validate_profile_photo -- 2MB
    size cap, extension, and signature check) and, unless the Celery task
    is mocked out, the real validation/promotion task also runs synchronously
    here since CELERY_TASK_ALWAYS_EAGER is on for tests -- so a successful
    upload lands as "ready" (or "failed") in the same request/response.

    The presigned-S3 two-step flow (request slot -> finalize) is disabled
    for now; see the commented-out branches in views.py/serializers.py.
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

    def _upload(self, name, content, content_type="image/jpeg", **extra):
        upload = make_upload(name, content, content_type=content_type)
        return self.client.post(self.request_url, {"file": upload, **extra}, format="multipart")

    def test_valid_jpeg_accepted(self):
        response = self._upload("a.jpg", make_image_bytes("JPEG"), content_type="image/jpeg")
        self.assertEqual(response.status_code, 201)
        photo_id = response.data["photo"]["id"]
        self.assertEqual(Photo.objects.get(pk=photo_id).status, "ready")

    def test_valid_png_accepted(self):
        response = self._upload("a.png", make_image_bytes("PNG"), content_type="image/png")
        self.assertEqual(response.status_code, 201)
        photo_id = response.data["photo"]["id"]
        self.assertEqual(Photo.objects.get(pk=photo_id).status, "ready")

    def test_valid_webp_accepted(self):
        response = self._upload("a.webp", make_image_bytes("WEBP"), content_type="image/webp")
        self.assertEqual(response.status_code, 201)
        photo_id = response.data["photo"]["id"]
        self.assertEqual(Photo.objects.get(pk=photo_id).status, "ready")

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

    def test_model_rejects_invalid_file_on_save(self):
        with self.assertRaises(DjangoValidationError):
            Photo.objects.create(
                profile=self.profile,
                file=SimpleUploadedFile("bad.jpg", NOT_AN_IMAGE, content_type="image/jpeg"),
            )

    def test_non_image_bytes_rejected(self):
        response = self._upload("fake.jpg", NOT_AN_IMAGE, content_type="image/jpeg")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Photo.objects.count(), 0)

    def test_oversized_file_rejected(self):
        oversized = make_image_bytes("JPEG") + b"\x00" * (3 * 1024 * 1024)
        response = self._upload("large.jpg", oversized, content_type="image/jpeg")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Photo.objects.count(), 0)

    def test_gallery_cap_of_six_enforced(self):
        with patch("apps.profiles.views.validate_and_promote_photo.delay"):
            for i in range(6):
                response = self._upload(f"{i}.jpg", make_image_bytes("JPEG"), content_type="image/jpeg")
                self.assertEqual(response.status_code, 201)
            seventh = self._upload("seventh.jpg", make_image_bytes("JPEG"), content_type="image/jpeg")
        self.assertEqual(seventh.status_code, 400)
        self.assertEqual(Photo.objects.count(), 6)

    def test_is_primary_single_primary_enforced(self):
        with patch("apps.profiles.views.validate_and_promote_photo.delay"):
            self._upload("first.jpg", make_image_bytes("JPEG"), content_type="image/jpeg", is_primary=True)
            second = self._upload("second.jpg", make_image_bytes("JPEG"), content_type="image/jpeg", is_primary=True)
        self.assertEqual(second.status_code, 201)
        photos = list(Photo.objects.filter(profile=self.profile))
        primaries = [p for p in photos if p.is_primary]
        self.assertEqual(len(primaries), 1)
