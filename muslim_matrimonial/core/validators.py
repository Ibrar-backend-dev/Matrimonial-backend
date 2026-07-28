from django.core.exceptions import ValidationError
from django.utils import timezone

from core.utils import calculate_age


MAX_PROFILE_PHOTO_SIZE = 2 * 1024 * 1024
ALLOWED_PROFILE_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def validate_adult_dob(value):
    if value >= timezone.localdate() or calculate_age(value) < 18:
        raise ValidationError("Users must be at least 18 years old.")


def validate_rating(value):
    if not 1 <= value <= 5:
        raise ValidationError("Rating must be between 1 and 5.")


def validate_image_file(value):
    header = value.read(12)
    value.seek(0)
    is_jpeg = header[:3] == b"\xff\xd8\xff"
    is_png = header[:8] == b"\x89PNG\r\n\x1a\n"
    is_webp = header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if not (is_jpeg or is_png or is_webp):
        raise ValidationError("The file is not a valid JPEG, PNG, or WEBP image.")


def validate_profile_photo(value):
    """Validate profile-photo size, extension, and file signature."""
    if value.size > MAX_PROFILE_PHOTO_SIZE:
        raise ValidationError("Profile photos must be 2 MB or smaller.")

    extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
    if extension not in ALLOWED_PROFILE_PHOTO_EXTENSIONS:
        raise ValidationError("Only JPEG, PNG, and WebP profile photos are allowed.")

    position = value.tell()
    header = value.read(12)
    value.seek(position)
    is_jpeg = header.startswith(b"\xff\xd8\xff")
    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if not (is_jpeg or is_png or is_webp):
        raise ValidationError("The uploaded file is not a valid JPEG, PNG, or WebP image.")
