from rest_framework import serializers

from .models import Verification


class VerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verification
        fields = (
            "id", "user", "phone_verified", "faith_declaration_accepted",
            "selfie_verified", "doc_url", "visit_status", "verified_by", "updated_at",
        )
        read_only_fields = ("id", "user", "phone_verified", "selfie_verified", "verified_by", "updated_at")


class AdminVerificationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_id = serializers.UUIDField(source="user.id", read_only=True)

    class Meta:
        model = Verification
        fields = (
            "id",
            "user",
            "user_id",
            "user_email",
            "phone_verified",
            "faith_declaration_accepted",
            "selfie_verified",
            "doc_url",
            "visit_status",
            "verified_by",
            "updated_at",
        )
        read_only_fields = ("id", "user", "verified_by", "updated_at")
