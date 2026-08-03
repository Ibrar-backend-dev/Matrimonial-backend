import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from core.validators import validate_adult_dob


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
        indexes = [
            # Matches the always-combined filter in eligible_profiles()
            # (apps/matches/services.py).
            models.Index(fields=["is_deleted", "gender", "is_muslim_confirmed"], name="profile_visibility_idx"),
            models.Index(fields=["dob"], name="profile_dob_idx"),
            models.Index(fields=["updated_at"], name="profile_updated_at_idx"),
            # Lower() indexes back the __iexact lookups on city/education --
            # a plain btree index isn't used by __iexact.
            models.Index(Lower("city"), name="profile_city_lower_idx"),
            models.Index(Lower("education"), name="profile_education_lower_idx"),
            models.Index(fields=["sect_maslak"], name="profile_sect_maslak_idx"),
        ]

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
        return self.photos.filter(status="ready").count()

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


class Photo(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="photos")
    # S3 object key, private bucket -- never a public URL. Points at the
    # quarantine object while status="pending", the promoted serving object
    # once status="ready". See core/media_storage.py and apps/profiles/tasks.py.
    storage_key = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    content_type = models.CharField(max_length=50, blank=True, null=True)
    width = models.PositiveIntegerField(blank=True, null=True)
    height = models.PositiveIntegerField(blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    privacy_level = models.CharField(max_length=20, choices=Profile.PHOTO_PRIVACY_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "photos"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            Photo.objects.filter(profile=self.profile, is_primary=True).exclude(pk=self.pk).update(is_primary=False)

    def delete(self, *args, **kwargs):
        from .tasks import delete_photo_object

        storage_key = self.storage_key
        super().delete(*args, **kwargs)
        if storage_key:
            delete_photo_object.delay(storage_key)


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
        indexes = [
            models.Index(fields=["interested_in"], name="pref_interested_in_idx"),
            models.Index(Lower("city_pref"), name="pref_city_lower_idx"),
            models.Index(Lower("education_pref"), name="pref_education_lower_idx"),
            models.Index(fields=["sect_pref"], name="pref_sect_pref_idx"),
        ]

    def clean(self):
        if self.age_range_min < 18 or self.age_range_min > self.age_range_max:
            raise ValidationError("The preferred age range is invalid.")
        if hasattr(self.user, "profile") and self.interested_in == self.user.profile.gender:
            raise ValidationError("Interest must be the opposite of the profile gender.")
