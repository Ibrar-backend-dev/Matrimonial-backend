from django.core.exceptions import ValidationError
from django.utils import timezone

from core.utils import calculate_age


def validate_adult_dob(value):
    if value >= timezone.localdate() or calculate_age(value) < 18:
        raise ValidationError("Users must be at least 18 years old.")


def validate_rating(value):
    if not 1 <= value <= 5:
        raise ValidationError("Rating must be between 1 and 5.")
