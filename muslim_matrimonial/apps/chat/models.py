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
    # Client-generated idempotency key for a WebSocket send: a retried send
    # (flaky reconnect) with the same key returns the already-persisted
    # message instead of creating a duplicate. Scoped to (match, sender) --
    # not globally unique -- so one user's key can't collide with another's.
    client_message_id = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        db_table = "messages"
        ordering = ("sent_at",)
        indexes = [
            models.Index(fields=["match", "sent_at"], name="message_match_sent_at_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "sender", "client_message_id"],
                condition=models.Q(client_message_id__isnull=False) & ~models.Q(client_message_id=""),
                name="unique_message_client_id_per_sender",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.match.status != "accepted":
            raise ValueError("Cannot send messages on a match that is not accepted.")
        if self.sender_id not in {self.match.sender_id, self.match.receiver_id}:
            raise ValueError("The message sender is not part of this match.")
        super().save(*args, **kwargs)
