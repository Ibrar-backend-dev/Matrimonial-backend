import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.validators import validate_adult_dob, validate_image_file


GENDER_CHOICES = [("male", "Male"), ("female", "Female")]


class Profile(models.Model):
    SECT_CHOICES = [
        ("sunni", "Sunni"),
        ("shia", "Shia"),
        ("deobandi", "Deobandi"),
        ("barelvi", "Barelvi"),
        ("salafi", "Salafi/Ahle Hadith"),
    ]
    MARITAL_STATUS_CHOICES = [
        ("never_married", "Never Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
    ]
    PHOTO_PRIVACY_CHOICES = [
        ("visible", "Always Visible"),
        ("blur_till_match", "Blurred Until Match"),
        ("always_blur", "Always Blurred"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    name = models.CharField(max_length=150)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    dob = models.DateField(validators=[validate_adult_dob])
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    sect_maslak = models.CharField(max_length=20, choices=SECT_CHOICES)
    education = models.CharField(max_length=150)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES)
    is_muslim_confirmed = models.BooleanField(default=False)
    photo_privacy_level = models.CharField(max_length=20, choices=PHOTO_PRIVACY_CHOICES, default="blur_till_match")
    profession = models.CharField(max_length=150, blank=True, null=True)
    ethnicity = models.CharField(max_length=100, blank=True, null=True)
    languages = models.CharField(max_length=255, blank=True, null=True)
    number_of_children = models.PositiveSmallIntegerField(blank=True, null=True)
    prayer_level = models.CharField(max_length=50, blank=True, null=True)
    hijab_beard_pref = models.CharField(max_length=50, blank=True, null=True)
    smoking_pref = models.CharField(max_length=20, blank=True, null=True)
    drinking_pref = models.CharField(max_length=20, blank=True, null=True)
    halal_meat_pref = models.BooleanField(default=True)
    willing_to_relocate = models.BooleanField(default=False)
    marriage_intentions = models.CharField(max_length=255, blank=True, null=True)
    wali_chaperone_required = models.BooleanField(default=False)
    bio = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "profiles"

    def __str__(self):
        return self.name

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def delete(self, *args, **kwargs):
        self.soft_delete()

    @property
    def photo_count(self):
        return self.photos.count()

    @property
    def is_complete(self):
        required_fields = [
            self.name,
            self.gender,
            self.dob,
            self.city,
            self.country,
            self.sect_maslak,
            self.education,
            self.marital_status,
        ]
        return all(required_fields) and self.photo_count >= 1


def photo_upload_path(instance, filename):
    header = instance.image.file.read(12)
    instance.image.file.seek(0)
    if header[:3] == b"\xff\xd8\xff":
        ext = "jpg"
    elif header[:8] == b"\x89PNG\r\n\x1a\n":
        ext = "png"
    elif header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        ext = "webp"
    else:
        ext = "bin"
    return f"profile_photos/{uuid.uuid4()}.{ext}"


class Photo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="photos")
    image = models.FileField(upload_to=photo_upload_path, blank=True, null=True, validators=[validate_image_file])
    is_primary = models.BooleanField(default=False)
    privacy_level = models.CharField(max_length=20, choices=Profile.PHOTO_PRIVACY_CHOICES, blank=True, null=True)

    class Meta:
        db_table = "photos"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            Photo.objects.filter(profile=self.profile, is_primary=True).exclude(pk=self.pk).update(is_primary=False)

    def delete(self, *args, **kwargs):
        image_name = self.image.name
        super().delete(*args, **kwargs)
        if image_name:
            self.image.storage.delete(image_name)


class Preference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preference")
    interested_in = models.CharField(max_length=10, choices=GENDER_CHOICES)
    age_range_min = models.PositiveSmallIntegerField(default=18)
    age_range_max = models.PositiveSmallIntegerField(default=60)
    city_pref = models.CharField(max_length=100, blank=True, null=True)
    education_pref = models.CharField(max_length=150, blank=True, null=True)
    sect_pref = models.CharField(max_length=20, choices=Profile.SECT_CHOICES, blank=True, null=True)

    class Meta:
        db_table = "preferences"

    def clean(self):
        if self.age_range_min < 18 or self.age_range_min > self.age_range_max:
            raise ValidationError("The preferred age range is invalid.")
        if hasattr(self.user, "profile") and self.interested_in == self.user.profile.gender:
            raise ValidationError("Interest must be the opposite of the profile gender.")
