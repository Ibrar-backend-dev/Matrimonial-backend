from rest_framework import serializers

from core import media_storage

from .models import PersonalPhoto

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class PersonalPhotoUploadRequestSerializer(serializers.Serializer):
    """Step 1 of the presigned-upload flow -- see core/media_uploads.py and
    core/validators.py:validate_profile_photo for the server-side re-encode
    (2MB max, EXIF strip, WEBP) that happens once /finalize is called."""

    content_type = serializers.ChoiceField(choices=sorted(ALLOWED_IMAGE_TYPES))
    caption = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    display_order = serializers.IntegerField(required=False, default=0, min_value=0)


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
