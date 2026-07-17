from celery import shared_task

from apps.users.models import User

from .services import get_daily_suggestions


@shared_task
def build_daily_suggestions():
    built = 0
    users = User.objects.filter(is_active=True, status="active", profile__isnull=False, preference__isnull=False)
    for user in users.iterator():
        get_daily_suggestions(user, refresh=True)
        built += 1
    return built
