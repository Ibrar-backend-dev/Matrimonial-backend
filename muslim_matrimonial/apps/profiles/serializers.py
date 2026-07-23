from rest_framework import serializers

from core.utils import calculate_age

from .models import Photo, Preference, Profile

from apps.matches.models import MatchRequest

MAX_PHOTO_SIZE = 2 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class PhotoSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(write_only=True, required=True)
    url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Photo
        fields = ("id", "image", "url", "is_primary", "privacy_level")
        read_only_fields = ("id", "url")

    def get_url(self, instance):
        request = self.context.get("request")
        if instance.image and request is not None:
            return request.build_absolute_uri(instance.image.url)
        return None

    def validate_image(self, value):
        if value.size > MAX_PHOTO_SIZE:
            raise serializers.ValidationError("Each photo must be 2 MB or smaller.")
        if value.content_type not in ALLOWED_IMAGE_TYPES:
            raise serializers.ValidationError("Supported image types are JPEG, PNG, and WEBP.")
        return value

    def validate(self, attrs):
        profile = self.context.get("profile")
        if profile and profile.photos.count() >= 6:
            raise serializers.ValidationError("A gallery may contain a maximum of 6 photos.")
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop("image", None)
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
    photos = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    is_complete = serializers.SerializerMethodField()
    photo_count = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "id", "user", "name", "gender", "dob", "age", "city", "country",
            "sect_maslak", "education", "marital_status", "is_muslim_confirmed",
            "photo_privacy_level", "profession", "ethnicity", "languages",
            "number_of_children", "prayer_level", "hijab_beard_pref", "smoking_pref",
            "drinking_pref", "halal_meat_pref", "willing_to_relocate",
            "marriage_intentions", "wali_chaperone_required", "bio", "photos",
            "photo_count", "is_complete", "created_at", "updated_at",
        )
        read_only_fields = ("id", "user", "age", "photo_count", "is_complete", "created_at", "updated_at")

    def get_age(self, obj) -> int:
        return calculate_age(obj.dob)

    def get_photos(self, obj):
        photos = obj.photos.all()[:6]
        return PhotoSerializer(photos, many=True, context=self.context).data

    def get_is_complete(self, obj):
        return obj.is_complete

    def get_photo_count(self, obj):
        return obj.photo_count

    def validate(self, attrs):
        gender = attrs.get("gender", getattr(self.instance, "gender", None))
        request = self.context.get("request")
        preference = getattr(getattr(request, "user", None), "preference", None)
        if preference and gender and preference.interested_in == gender:
            raise serializers.ValidationError({"gender": "Gender cannot be the same as the selected interest."})
        return attrs

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
