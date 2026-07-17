import uuid

from django.conf import settings
from django.db import models


class Subscription(models.Model):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("premium", "Premium"),
        ("matchmaker_assisted", "Matchmaker Assisted"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan_type = models.CharField(max_length=30, choices=PLAN_CHOICES, default="free")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="active")

    class Meta:
        db_table = "subscriptions"
