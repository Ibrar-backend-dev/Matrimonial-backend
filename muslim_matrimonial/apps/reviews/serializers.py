from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ("id", "user", "app_rating", "comment", "is_public", "created_at")
        read_only_fields = ("id", "user", "is_public", "created_at")
