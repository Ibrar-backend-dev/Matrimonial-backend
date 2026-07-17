from rest_framework import serializers

from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ("id", "reporter", "reported", "reason", "created_at")
        read_only_fields = ("id", "reporter", "created_at")

    def validate_reported(self, value):
        if value == self.context["request"].user:
            raise serializers.ValidationError("A user cannot report themselves.")
        if not value.is_active or value.status != "active":
            raise serializers.ValidationError("The reported account is unavailable.")
        return value
