import tempfile
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from core.validators import validate_image_file

from .models import Photo, Profile

User = get_user_model()

JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
WEBP_HEADER = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20
NOT_AN_IMAGE = b"This is definitely not an image, just plain text bytes." * 2
BIG_JPEG = JPEG_HEADER + b"\x00" * (3 * 1024 * 1024)


def make_upload(name, content, content_type="image/jpeg"):
    return SimpleUploadedFile(name, content, content_type=content_type)


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


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PhotoUploadViewTests(TestCase):
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
        self.upload_url = reverse("profiles:upload-photo")

    def _upload(self, content, name="photo.jpg", content_type="image/jpeg", **extra):
        return self.client.post(
            self.upload_url,
            {"image": make_upload(name, content, content_type), **extra},
            format="multipart",
        )

    def test_valid_jpeg_accepted(self):
        response = self._upload(JPEG_HEADER)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Photo.objects.count(), 1)

    def test_valid_png_accepted(self):
        response = self._upload(PNG_HEADER, name="photo.png", content_type="image/png")
        self.assertEqual(response.status_code, 201)

    def test_valid_webp_accepted(self):
        response = self._upload(WEBP_HEADER, name="photo.webp", content_type="image/webp")
        self.assertEqual(response.status_code, 201)

    def test_non_image_bytes_rejected(self):
        response = self._upload(NOT_AN_IMAGE)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Photo.objects.count(), 0)

    def test_fake_jpg_extension_text_content_rejected(self):
        response = self._upload(NOT_AN_IMAGE, name="fake.jpg", content_type="image/jpeg")
        self.assertEqual(response.status_code, 400)

    def test_oversized_file_rejected(self):
        response = self._upload(BIG_JPEG)
        self.assertEqual(response.status_code, 400)

    def test_gallery_cap_of_six_enforced(self):
        for _ in range(6):
            self._upload(JPEG_HEADER, name=f"{uuid.uuid4()}.jpg")
        response = self._upload(JPEG_HEADER, name="seventh.jpg")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Photo.objects.count(), 6)

    def test_is_primary_single_primary_enforced(self):
        self._upload(JPEG_HEADER, name="one.jpg", is_primary=True)
        response = self._upload(JPEG_HEADER, name="two.jpg", is_primary=True)
        self.assertEqual(response.status_code, 201)
        photos = list(Photo.objects.filter(profile=self.profile))
        primaries = [p for p in photos if p.is_primary]
        self.assertEqual(len(primaries), 1)
