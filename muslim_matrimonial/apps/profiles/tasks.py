import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core import media_storage
from core.media_validation import MediaValidationError, validate_and_normalize

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    acks_late=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def validate_and_promote_photo(self, photo_id):
    from .models import Photo

    photo = Photo.objects.filter(pk=photo_id).select_related("profile").first()
    if not photo or photo.status != "pending":
        return

    try:
        data = media_storage.get_object_bytes(photo.storage_key)
    except Exception as exc:
        logger.exception("Could not fetch quarantined photo %s from storage", photo_id)
        raise self.retry(exc=exc)

    try:
        clean_data, width, height = validate_and_normalize(data, settings.MEDIA_UPLOAD_MAX_BYTES)
    except MediaValidationError:
        media_storage.delete_object(photo.storage_key)
        photo.status = "failed"
        photo.storage_key = None
        photo.save(update_fields=["status", "storage_key"])
        return

    new_key = media_storage.serving_key("profile_photos", photo.profile.user_id)
    media_storage.put_object_bytes(new_key, clean_data, "image/webp")
    media_storage.delete_object(photo.storage_key)

    photo.storage_key = new_key
    photo.status = "ready"
    photo.content_type = "image/webp"
    photo.width = width
    photo.height = height
    photo.save(update_fields=["storage_key", "status", "content_type", "width", "height"])


@shared_task(acks_late=True)
def delete_photo_object(storage_key):
    media_storage.delete_object(storage_key)


@shared_task
def sweep_abandoned_photo_uploads():
    from .models import Photo

    cutoff = timezone.now() - timedelta(hours=settings.MEDIA_QUARANTINE_EXPIRY_HOURS)
    swept = 0
    for photo in Photo.objects.filter(status="pending", created_at__lt=cutoff).iterator():
        # Photo.delete() enqueues the S3 cleanup itself -- no need to call
        # media_storage.delete_object() here too.
        photo.delete()
        swept += 1
    return swept
