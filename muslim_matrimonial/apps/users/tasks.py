import logging
import secrets

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)
OTP_TTL_SECONDS = 600


def otp_cache_key(phone, purpose):
    return f"otp:{purpose}:{phone}"


def issue_otp(phone, purpose="verify"):
    otp = f"{secrets.randbelow(1_000_000):06d}"
    cache.set(otp_cache_key(phone, purpose), otp, OTP_TTL_SECONDS)
    try:
        send_otp.delay(phone, otp, purpose)
    except Exception:
        logger.exception("OTP task could not be queued for %s", phone)
    return otp


@shared_task
def send_otp(phone, otp, purpose="verify"):
    # Replace this log-only adapter with an approved SMS provider in deployment.
    logger.info("OTP dispatch requested for %s (%s)", phone, purpose)
    return True
