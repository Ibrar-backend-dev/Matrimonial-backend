import logging

from celery import shared_task

from apps.users.models import User
from core.locks import distributed_lock

from .services import get_daily_suggestions

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    acks_late=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def build_daily_suggestions(self):
    # get_daily_suggestions(refresh=True) is itself idempotent (it overwrites
    # the cached suggestion list), so a genuine double-run isn't destructive --
    # this lock just avoids wasted duplicate work if two Beat processes
    # briefly overlap during a deploy, per the plan's Beat-correctness note.
    try:
        with distributed_lock("build-daily-suggestions", timeout=3600, blocking_timeout=0):
            built = 0
            users = User.objects.filter(
                is_active=True, status="active", profile__isnull=False, preference__isnull=False
            )
            for user in users.iterator():
                get_daily_suggestions(user, refresh=True)
                built += 1
            return built
    except RuntimeError:
        logger.info("build_daily_suggestions already running elsewhere; skipping duplicate run")
        return 0
