import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import config as env_config
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-secret-key-change-before-production")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "channels",
    "corsheaders",
    "apps.users",
    "apps.profiles",
    "apps.verifications",
    "apps.matches",
    "apps.chat",
    "apps.gallery",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "0")),
        )
    }
else:
    POSTGRES_DB = os.getenv("POSTGRES_DB")
    if not POSTGRES_DB:
        raise ImproperlyConfigured(
            "Postgres database not configured. Set DATABASE_URL, or POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST and POSTGRES_PORT environment variables."
        )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": POSTGRES_DB,
            "USER": os.getenv("POSTGRES_USER"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "0")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Karachi")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "/media/"
# Temporary local media storage for development.
# When AWS_STORAGE_BUCKET_NAME is unset, uploaded photos are saved under the
# project root media folder so the app can run without S3 during development.
MEDIA_ROOT = BASE_DIR.parent / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "otp_email": "40/hour",
        "auth": "50/hour",
        "auth_authenticated": "50/hour",
        "profile": "50/hour",
        "match": "50/hour",
        "chat": "50/minute",
    },
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=36500),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=36500),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Muslim Matrimonial API",
    "VERSION": "1.0.0",
    "ENUM_NAME_OVERRIDES": {
        "GenderEnum": "apps.profiles.models.GENDER_CHOICES",
        "SectMaslakEnum": "apps.profiles.models.Profile.SECT_CHOICES",
        "PrivacyLevelEnum": "apps.profiles.models.Profile.PHOTO_PRIVACY_CHOICES",
    },
}

def _redis_url(env_var, fallback_db):
    """Resolve a Redis connection URL for one logical workload (cache/celery/channels).

    Each workload has its own env var so it can be pointed at a fully separate
    Redis instance later (e.g. splitting the Celery broker off) without touching
    application code -- only the env var changes. REDIS_HOST/REDIS_PORT remain as
    the local-dev fallback (single Redis container, separated by db number).
    """
    explicit = os.getenv(env_var)
    if explicit:
        if not explicit.startswith(("redis://", "rediss://", "unix://")):
            raise ImproperlyConfigured(
                f"{env_var} is set but is not a valid Redis URL: {explicit!r}. "
                "Check that any ${{Service.VAR}} reference used to build it actually resolves."
            )
        return explicit
    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = os.getenv("REDIS_PORT", "6379")
    return f"redis://{host}:{port}/{fallback_db}"


# REDIS_ENABLED/CELERY_ENABLED: escape hatch for a smoke-test deploy that has
# no Redis/worker provisioned yet -- flip these off so the web process never
# tries to dial Redis (cache/channels fall back to per-process backends) and
# Celery tasks run inline instead of being queued to a broker that doesn't
# exist. CELERY_ENABLED is forced off whenever Redis is, since there is no
# broker to talk to without it. NOT a substitute for the real thing once more
# than one web process is running -- see the else branches below.
REDIS_ENABLED = env_bool("REDIS_ENABLED", True)
CELERY_ENABLED = env_bool("CELERY_ENABLED", True) and REDIS_ENABLED

# Two logical Redis roles at launch (see plan: eviction policy is instance-wide,
# not per-db, so cache/throttling and the Celery broker must not share an
# instance in production even though they can share one in local dev):
#   - REDIS_CACHE_URL: Django cache + DRF throttling (+ Channels, until it needs
#     its own instance -- see REDIS_CHANNELS_URL below).
#   - REDIS_CELERY_URL: Celery broker/result backend. In production this should
#     point at a dedicated instance configured with `noeviction` + persistence,
#     since losing queued/in-flight tasks to an LRU eviction is unacceptable.
#   - REDIS_CHANNELS_URL: Channels layer. Defaults to the cache instance (its
#     own logical db) but is independently switchable to a third instance later
#     purely via env var once WebSocket volume grows.
if REDIS_ENABLED:
    REDIS_CACHE_URL = _redis_url("REDIS_CACHE_URL", 0)
    REDIS_CELERY_URL = _redis_url("REDIS_CELERY_URL", 1)
    REDIS_CHANNELS_URL = _redis_url("REDIS_CHANNELS_URL", 2)

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_CHANNELS_URL],
                # Raised above the library default (100) for burst tolerance in
                # active chat rooms; retune based on Phase 11 load-test results.
                "capacity": int(os.getenv("CHANNELS_LAYER_CAPACITY", "300")),
                "expiry": int(os.getenv("CHANNELS_LAYER_EXPIRY", "60")),
            },
        }
    }
    CELERY_BROKER_URL = REDIS_CELERY_URL
    CELERY_RESULT_BACKEND = REDIS_CELERY_URL
else:
    # In-memory fallbacks: fine for a single-process smoke-test deploy, but
    # cache/channel state isn't shared across processes and chat/typing
    # events across processes are lost -- provision real Redis before scaling
    # past one web process.
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None

CELERY_TASK_ALWAYS_EAGER = env_config("CELERY_TASK_ALWAYS_EAGER", default=DEBUG, cast=bool) or not CELERY_ENABLED
CELERY_BEAT_SCHEDULE = {
    "build-daily-match-suggestions": {
        "task": "apps.matches.tasks.build_daily_suggestions",
        "schedule": 86400.0,
    },
    "sweep-abandoned-profile-photo-uploads": {
        "task": "apps.profiles.tasks.sweep_abandoned_photo_uploads",
        "schedule": 3600.0,
    },
    "sweep-abandoned-personal-photo-uploads": {
        "task": "apps.gallery.tasks.sweep_abandoned_personal_photo_uploads",
        "schedule": 3600.0,
    },
}

# Dedicated queues so a burst of media/batch work can never delay OTP/auth
# email delivery -- run `celery -A config worker -Q critical,default,media,batch`
# (or separate worker processes per queue) rather than the single implicit
# queue Celery uses by default.
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.users.tasks.send_otp": {"queue": "critical"},
    "apps.matches.tasks.build_daily_suggestions": {"queue": "batch"},
    "apps.profiles.tasks.validate_and_promote_photo": {"queue": "media"},
    "apps.profiles.tasks.delete_photo_object": {"queue": "media"},
    "apps.profiles.tasks.sweep_abandoned_photo_uploads": {"queue": "batch"},
    "apps.gallery.tasks.validate_and_promote_personal_photo": {"queue": "media"},
    "apps.gallery.tasks.delete_personal_photo_object": {"queue": "media"},
    "apps.gallery.tasks.sweep_abandoned_personal_photo_uploads": {"queue": "batch"},
}

# Reliability: a killed/restarted worker redelivers its in-flight task
# (acks_late) instead of losing it, bounded by a low prefetch multiplier so a
# slow worker doesn't hoard tasks it can't get to promptly. visibility_timeout
# must exceed the slowest expected task's runtime, or the broker will
# redeliver a still-running task to another worker.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": int(os.getenv("CELERY_VISIBILITY_TIMEOUT_SECONDS", "3600")),
}

if REDIS_ENABLED:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_CACHE_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CORS_ALLOWED_ORIGINS = [origin for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin]

# Media: private S3 bucket, presigned direct-to-S3 uploads (client never
# sends file bytes through Django), CloudFront for private signed delivery.
# There is no public serving path -- every photo, regardless of its
# privacy_level, is only ever reachable via a short-lived signed URL minted
# after a Django-side authorization check.
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
# Local development uses MEDIA_ROOT storage when AWS_STORAGE_BUCKET_NAME is
# unset. Set AWS_STORAGE_BUCKET_NAME to enable S3-backed photo storage.
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_QUARANTINE_PREFIX = os.getenv("AWS_S3_QUARANTINE_PREFIX", "quarantine")
CLOUDFRONT_DOMAIN = os.getenv("CLOUDFRONT_DOMAIN", "")
CLOUDFRONT_KEY_PAIR_ID = os.getenv("CLOUDFRONT_KEY_PAIR_ID", "")
CLOUDFRONT_PRIVATE_KEY = os.getenv("CLOUDFRONT_PRIVATE_KEY", "")
MEDIA_UPLOAD_MAX_BYTES = int(os.getenv("MEDIA_UPLOAD_MAX_BYTES", str(2 * 1024 * 1024)))
MEDIA_UPLOAD_URL_TTL_SECONDS = int(os.getenv("MEDIA_UPLOAD_URL_TTL_SECONDS", "300"))
MEDIA_SIGNED_URL_TTL_SECONDS = int(os.getenv("MEDIA_SIGNED_URL_TTL_SECONDS", "300"))
MEDIA_QUARANTINE_EXPIRY_HOURS = int(os.getenv("MEDIA_QUARANTINE_EXPIRY_HOURS", "24"))
MAX_PROFILE_GALLERY_PHOTOS = 6
MAX_PERSONAL_GALLERY_PHOTOS = 6

EMAIL_BACKEND = env_config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env_config("EMAIL_HOST", default="")
EMAIL_PORT = env_config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = env_config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = env_config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = env_config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env_config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env_config("DEFAULT_FROM_EMAIL", default="no-reply@muslimmatrimonial.local")
EMAIL_TIMEOUT = env_config("EMAIL_TIMEOUT", default=10, cast=int)
