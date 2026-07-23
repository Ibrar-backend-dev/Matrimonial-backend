import logging
import secrets

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)
OTP_TTL_SECONDS = 600


def otp_cache_key(email, purpose):
    return f"otp:{purpose}:{email}"


def issue_otp(email, purpose="verify"):
    otp = f"{secrets.randbelow(1_000_000):06d}"
    cache.set(otp_cache_key(email, purpose), otp, OTP_TTL_SECONDS)
    try:
        send_otp.delay(email, otp, purpose)
    except Exception:
        logger.exception("OTP task could not be queued for %s", email)
    return otp


@shared_task
def send_otp(email, otp, purpose="verify"):
    # Replace this log-only adapter with an approved email provider in deployment.
    logger.info("OTP dispatch requested for %s (%s)", email, purpose)
    return True
