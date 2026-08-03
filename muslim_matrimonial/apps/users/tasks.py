import logging
import secrets

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)
OTP_TTL_SECONDS = 600

PURPOSE_COPY = {
    "verify": ("Verify your email address", "Welcome to Muslim Matrimonial! Use the code below to verify your email address."),
    "password-reset": ("Reset your password", "We received a request to reset your password. Use the code below to continue."),
}
DEFAULT_SUBJECT = "Your verification code"
DEFAULT_INTRO = "Use the code below to continue."


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


def _build_otp_email(otp, purpose):
    subject, intro = PURPOSE_COPY.get(purpose, (DEFAULT_SUBJECT, DEFAULT_INTRO))
    ttl_minutes = OTP_TTL_SECONDS // 60
    text_body = (
        f"{intro}\n\n"
        f"    {otp}\n\n"
        f"This code expires in {ttl_minutes} minutes. "
        "If you didn't request this, you can safely ignore this email.\n\n"
        "- Muslim Matrimonial"
    )
    html_body = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;padding:32px;">
            <tr><td style="font-size:18px;font-weight:bold;color:#1a1a1a;padding-bottom:12px;">Muslim Matrimonial</td></tr>
            <tr><td style="font-size:14px;color:#333333;line-height:1.5;padding-bottom:20px;">{intro}</td></tr>
            <tr>
              <td align="center" style="padding:16px 0;">
                <span style="display:inline-block;font-size:32px;font-weight:bold;letter-spacing:6px;color:#0f5132;background:#e8f5e9;padding:12px 24px;border-radius:6px;">{otp}</span>
              </td>
            </tr>
            <tr>
              <td style="font-size:12px;color:#777777;padding-top:20px;">
                This code expires in {ttl_minutes} minutes. If you didn't request this, you can safely ignore this email.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return subject, text_body, html_body


@shared_task(
    bind=True,
    acks_late=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def send_otp(self, email, otp, purpose="verify"):
    if cache.get(otp_cache_key(email, purpose)) != otp:
        logger.info("Skipping stale OTP email for %s (%s); superseded or expired", email, purpose)
        return False

    subject, text_body, html_body = _build_otp_email(otp, purpose)
    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [email])
    message.attach_alternative(html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        logger.exception("Failed to send OTP email to %s", email)
        raise self.retry(exc=exc)
    return True
