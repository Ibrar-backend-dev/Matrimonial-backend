from rest_framework import serializers

from core.validators import validate_profile_photo

from .models import PersonalPhoto


class PersonalPhotoSerializer(serializers.ModelSerializer):
    image = serializers.FileField(required=False, validators=[validate_profile_photo])

    class Meta:
        model = PersonalPhoto
        fields = ("id", "image", "caption", "display_order", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        if self.instance is None and "image" not in attrs:
            raise serializers.ValidationError({"image": "This field is required."})
        return attrs


class GalleryAccessSerializer(serializers.Serializer):
    match_request_id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    has_access = serializers.BooleanField(read_only=True)
