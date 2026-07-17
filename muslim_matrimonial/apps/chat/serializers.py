from rest_framework import serializers

from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("id", "match", "sender", "message", "sent_at", "read_status")
        read_only_fields = fields
