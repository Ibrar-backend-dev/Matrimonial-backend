import uuid

from django.conf import settings
from django.db import models

from apps.matches.models import MatchRequest


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(MatchRequest, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    read_status = models.BooleanField(default=False)

    class Meta:
        db_table = "messages"
        ordering = ("sent_at",)

    def save(self, *args, **kwargs):
        if self.match.status != "accepted":
            raise ValueError("Cannot send messages on a match that is not accepted.")
        if self.sender_id not in {self.match.sender_id, self.match.receiver_id}:
            raise ValueError("The message sender is not part of this match.")
        super().save(*args, **kwargs)
