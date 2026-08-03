import logging
import os

from celery import Celery
from celery.signals import task_failure

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

app = Celery("muslim_matrimonial")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

logger = logging.getLogger("celery.failed_task")


@task_failure.connect
def _log_exhausted_task(sender=None, task_id=None, exception=None, **kwargs):
    # Fires once a task has permanently failed (retries exhausted, or a
    # non-retryable exception) -- never let a task fail silently. Phase 10's
    # Sentry CeleryIntegration also hooks this signal and reports it as an
    # error/alert once wired up; this logger is the fallback until then.
    logger.critical(
        "Task %s (id=%s) failed permanently: %s", getattr(sender, "name", sender), task_id, exception
    )
