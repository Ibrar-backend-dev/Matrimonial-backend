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
    class Meta:
        model = Verification
        fields = "__all__"
        read_only_fields = ("id", "user", "updated_at")
