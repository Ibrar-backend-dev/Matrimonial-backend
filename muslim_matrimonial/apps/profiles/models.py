import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

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

    class Meta:
        db_table = "profiles"

    def __str__(self):
        return self.name


class Photo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="photos")
    url = models.URLField()
    is_primary = models.BooleanField(default=False)
    privacy_level = models.CharField(max_length=20, choices=Profile.PHOTO_PRIVACY_CHOICES, blank=True, null=True)

    class Meta:
        db_table = "photos"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            Photo.objects.filter(profile=self.profile, is_primary=True).exclude(pk=self.pk).update(is_primary=False)


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
