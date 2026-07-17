from rest_framework import serializers

from core.utils import calculate_age

from .models import Photo, Preference, Profile

from apps.matches.models import MatchRequest

class PhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Photo
        fields = ("id", "url", "is_primary", "privacy_level")
        read_only_fields = ("id",)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        level = instance.privacy_level or instance.profile.photo_privacy_level
        can_see = bool(viewer and viewer.is_authenticated and (viewer == instance.profile.user or viewer.is_staff))
        if not can_see and viewer and viewer.is_authenticated and level == "blur_till_match":
            

            can_see = MatchRequest.objects.filter(
                status="accepted",
                sender__in=[viewer, instance.profile.user],
                receiver__in=[viewer, instance.profile.user],
            ).exists()
        if level == "always_blur" or (level == "blur_till_match" and not can_see):
            data["url"] = None
            data["is_blurred"] = True
        else:
            data["is_blurred"] = False
        return data


class ProfileSerializer(serializers.ModelSerializer):
    photos = PhotoSerializer(many=True, read_only=True)
    age = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "id", "user", "name", "gender", "dob", "age", "city", "country",
            "sect_maslak", "education", "marital_status", "is_muslim_confirmed",
            "photo_privacy_level", "profession", "ethnicity", "languages",
            "number_of_children", "prayer_level", "hijab_beard_pref", "smoking_pref",
            "drinking_pref", "halal_meat_pref", "willing_to_relocate",
            "marriage_intentions", "wali_chaperone_required", "bio", "photos",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "user", "age", "created_at", "updated_at")

    def get_age(self, obj) -> int:
        return calculate_age(obj.dob)

    def validate_gender(self, value):
        request = self.context.get("request")
        preference = getattr(getattr(request, "user", None), "preference", None)
        if preference and preference.interested_in == value:
            raise serializers.ValidationError("Gender cannot be the same as the selected interest.")
        return value


class ProfilePrivacySerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("photo_privacy_level", "wali_chaperone_required")


class PreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Preference
        fields = ("id", "interested_in", "age_range_min", "age_range_max", "city_pref", "education_pref", "sect_pref")
        read_only_fields = ("id",)

    def validate(self, attrs):
        instance = self.instance
        minimum = attrs.get("age_range_min", getattr(instance, "age_range_min", 18))
        maximum = attrs.get("age_range_max", getattr(instance, "age_range_max", 60))
        if minimum < 18 or minimum > maximum:
            raise serializers.ValidationError("The preferred age range is invalid.")
        request = self.context.get("request")
        profile = getattr(getattr(request, "user", None), "profile", None)
        interest = attrs.get("interested_in", getattr(instance, "interested_in", None))
        if profile and interest == profile.gender:
            raise serializers.ValidationError({"interested_in": "Interest must be the opposite of profile gender."})
        return attrs
