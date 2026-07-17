import uuid

from django.conf import settings
from django.db import models


class Verification(models.Model):
    VISIT_STATUS_CHOICES = [
        ("not_requested", "Not Requested"),
        ("pending", "Pending"),
        ("done", "Done"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="verification")
    phone_verified = models.BooleanField(default=False)
    faith_declaration_accepted = models.BooleanField(default=False)
    selfie_verified = models.BooleanField(default=False)
    doc_url = models.URLField(blank=True, null=True)
    visit_status = models.CharField(max_length=20, choices=VISIT_STATUS_CHOICES, default="not_requested")
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verifications_approved",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "verifications"
