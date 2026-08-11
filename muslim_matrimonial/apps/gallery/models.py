import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.validators import validate_profile_photo


class PersonalPhoto(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_photos",
    )
    # S3 object key, private bucket. Points at the quarantine object while
    # status="pending", the promoted serving object once status="ready".
    # See core/media_storage.py and apps/gallery/tasks.py.
    storage_key = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(upload_to="gallery_photos/%Y/%m/%d/", blank=True, null=True, validators=[validate_profile_photo])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    content_type = models.CharField(max_length=50, blank=True, null=True)
    width = models.PositiveIntegerField(blank=True, null=True)
    height = models.PositiveIntegerField(blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "personal_photos"
        ordering = ("display_order", "created_at")

    def clean(self):
        super().clean()
        if self.file:
            validate_profile_photo(self.file)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from .tasks import delete_personal_photo_object

        storage_key = self.storage_key
        super().delete(*args, **kwargs)
        if storage_key:
            delete_personal_photo_object.delay(storage_key)


class GalleryAccess(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gallery_access_grants",
    )
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gallery_access_received",
    )
    match_request = models.ForeignKey(
        "matches.MatchRequest",
        on_delete=models.CASCADE,
        related_name="gallery_access_grants",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gallery_access"
        indexes = [
            models.Index(fields=["viewer"], name="gallery_access_viewer_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "match_request"),
                name="unique_gallery_access_per_owner_match",
            ),
            models.CheckConstraint(
                check=~models.Q(owner=models.F("viewer")),
                name="gallery_owner_and_viewer_differ",
            ),
        ]

    def clean(self):
        match = self.match_request
        if match.status != "accepted":
            raise ValidationError("Gallery access requires an accepted match.")
        participants = {match.sender_id, match.receiver_id}
        if {self.owner_id, self.viewer_id} != participants:
            raise ValidationError("The gallery owner and viewer must be participants in the match.")
