from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.users.models import User

from . import media_storage


def reserve_upload_slot(model, owner_field, owner, user, max_count, key_prefix, content_type):
    """Atomically reserve a gallery slot and return (photo, presigned_post).

    Locks `user`'s User row as a mutex so two concurrent presign requests
    can't both observe count < max_count and both succeed -- the slot is
    reserved (a `status="pending"` row created) inside the same transaction
    as the count check, before the client has uploaded any bytes.

    `owner`/`owner_field` describe the FK the photo model actually stores
    (e.g. Photo.profile is a Profile, PersonalPhoto.user is a User) --
    `user` is always the underlying User, since that's what's safe to lock
    regardless of which model the FK points at.
    """
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        current_count = model.objects.filter(**{owner_field: owner}).exclude(status="failed").count()
        if current_count >= max_count:
            raise ValidationError(f"A gallery may contain a maximum of {max_count} photos.")
        key = media_storage.quarantine_key(key_prefix, user.pk, content_type)
        photo = model.objects.create(**{owner_field: owner, "storage_key": key, "content_type": content_type})
    post = media_storage.create_presigned_post(key, content_type, settings.MEDIA_UPLOAD_MAX_BYTES)
    return photo, post


def finalize_upload(photo, validate_task):
    if photo.status != "pending":
        raise ValidationError("This upload has already been finalized.")
    if media_storage.head_object(photo.storage_key) is None:
        raise ValidationError("The file was not found in storage -- upload may have failed or expired.")
    validate_task.delay(str(photo.pk))
    # In real (non-eager) deployments the task hasn't run yet by the time we
    # respond -- this stays "pending" and the client polls/refetches. Under
    # CELERY_TASK_ALWAYS_EAGER (tests), the task has already completed and
    # mutated the DB row by the time .delay() returns, so this reflects that.
    photo.refresh_from_db()
    return photo
