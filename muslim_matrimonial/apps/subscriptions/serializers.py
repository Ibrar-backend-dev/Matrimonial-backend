from django.utils import timezone
from rest_framework import serializers

from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    start_date = serializers.DateTimeField(required=False, default=timezone.now)

    class Meta:
        model = Subscription
        fields = ("id", "user", "plan_type", "start_date", "end_date", "payment_status")
        read_only_fields = ("id", "user", "payment_status")

    def validate(self, attrs):
        if attrs.get("end_date") and attrs["end_date"] <= attrs.get("start_date", timezone.now()):
            raise serializers.ValidationError("end_date must be later than start_date.")
        return attrs


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ("payment_status",)
