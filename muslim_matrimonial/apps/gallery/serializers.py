from rest_framework import serializers

from core import media_storage
from core.validators import validate_profile_photo

from .models import PersonalPhoto

# ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}  -- only needed by the presigned-upload mode below


class PersonalPhotoUploadRequestSerializer(serializers.Serializer):
    """Direct file upload only, for local-dev/testing. See core/validators.py:validate_profile_photo
    for the 2MB size / extension / file-signature checks."""

    file = serializers.FileField(validators=[validate_profile_photo])
    caption = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    display_order = serializers.IntegerField(required=False, default=0, min_value=0)

    # --- Presigned S3 upload mode (disabled for now -- direct upload only) ---
    # content_type = serializers.ChoiceField(choices=sorted(ALLOWED_IMAGE_TYPES), required=False)
    #
    # def validate(self, attrs):
    #     if not attrs.get("file") and not attrs.get("content_type"):
    #         raise serializers.ValidationError("A file upload or content_type is required.")
    #     return attrs


class PersonalPhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PersonalPhoto
        fields = ("id", "url", "status", "caption", "display_order", "width", "height", "created_at", "updated_at")
        read_only_fields = ("id", "url", "status", "width", "height", "created_at", "updated_at")

    def get_url(self, instance):
        if instance.status != "ready":
            return None
        return media_storage.signed_delivery_url(instance.storage_key)


class GalleryAccessSerializer(serializers.Serializer):
    match_request_id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    has_access = serializers.BooleanField(read_only=True)
