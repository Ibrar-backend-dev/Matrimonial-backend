from rest_framework import serializers

from apps.profiles.models import GENDER_CHOICES, Profile

from .models import MatchRequest


class MatchRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchRequest
        fields = ("id", "sender", "receiver", "status", "created_at", "responded_at")
        read_only_fields = fields


class MatchResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("accepted", "rejected"))


class MatchFilterSerializer(serializers.Serializer):
    interested_in = serializers.ChoiceField(choices=GENDER_CHOICES, required=False)
    age_range_min = serializers.IntegerField(min_value=18, max_value=120, required=False)
    age_range_max = serializers.IntegerField(min_value=18, max_value=120, required=False)
    city_pref = serializers.CharField(max_length=100, allow_blank=True, required=False)
    education_pref = serializers.CharField(max_length=150, allow_blank=True, required=False)
    sect_pref = serializers.ChoiceField(choices=Profile.SECT_CHOICES, allow_blank=True, required=False)

    def validate(self, attrs):
        request = self.context.get("request")
        profile = getattr(getattr(request, "user", None), "profile", None)
        if profile and attrs.get("interested_in") == profile.gender:
            raise serializers.ValidationError({"interested_in": "Interest must be the opposite of profile gender."})
        minimum = attrs.get("age_range_min")
        maximum = attrs.get("age_range_max")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise serializers.ValidationError("The preferred age range is invalid.")
        return attrs
