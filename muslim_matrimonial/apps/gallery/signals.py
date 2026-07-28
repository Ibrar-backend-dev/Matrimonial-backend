from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import PersonalPhoto


def delete_file_after_commit(storage, name):
    if name:
        transaction.on_commit(lambda: storage.delete(name))


@receiver(pre_save, sender=PersonalPhoto)
def delete_replaced_photo(sender, instance, **kwargs):
    if not instance.pk:
        return
    old = sender.objects.filter(pk=instance.pk).only("image").first()
    if old and old.image.name and old.image.name != instance.image.name:
        delete_file_after_commit(old.image.storage, old.image.name)


@receiver(post_delete, sender=PersonalPhoto)
def delete_removed_photo(sender, instance, **kwargs):
    if instance.image:
        delete_file_after_commit(instance.image.storage, instance.image.name)
