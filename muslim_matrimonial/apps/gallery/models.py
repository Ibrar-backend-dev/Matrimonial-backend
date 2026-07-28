import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.validators import validate_profile_photo


class PersonalPhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_photos",
    )
    image = models.FileField(upload_to="personal_photos/", validators=[validate_profile_photo])
    caption = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "personal_photos"
        ordering = ("display_order", "created_at")


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
