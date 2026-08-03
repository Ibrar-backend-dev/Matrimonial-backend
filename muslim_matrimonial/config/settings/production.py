import os

from .base import *  # noqa: F403

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "3600"))
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

if CELERY_TASK_ALWAYS_EAGER:  # noqa: F405
    # .env.example ships this =true for local/test convenience. Failing fast
    # here catches the case where that value leaks into a real deployment's
    # env vars instead of relying on the DEBUG-based default in base.py --
    # eager mode runs OTP email/thumbnail/suggestion tasks synchronously
    # inside the request cycle, which silently destroys the latency targets
    # this app is being scaled for.
    raise RuntimeError(
        "CELERY_TASK_ALWAYS_EAGER must be false in production -- set it explicitly "
        "in this environment's env vars."
    )
