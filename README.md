# Muslim Matrimonial Backend

A Django REST Framework backend for a Muslim matrimonial platform: JWT-based
authentication with email OTP verification, profile management with privacy-aware
photo galleries, a separate personal photo gallery with match-gated sharing,
identity verification review, reciprocal match discovery, real-time chat over
WebSockets, subscriptions, reviews, and abuse reports.

## Tech stack

| Concern             | Technology                                              |
|----------------------|----------------------------------------------------------|
| Framework            | Django 5.0, Django REST Framework 3.15                  |
| Auth                 | `djangorestframework-simplejwt` (access + refresh tokens) |
| Real-time            | Django Channels 4 + `channels-redis` (ASGI, WebSockets)  |
| Background jobs      | Celery 5 + Celery Beat, Redis as broker/result backend, dedicated queues per workload |
| Database             | PostgreSQL (via `psycopg2`) in production, SQLite for local dev fallback |
| Caching / throttling | Redis-backed Django cache (`django-redis`)               |
| CORS                 | `django-cors-headers`                                    |
| API docs             | `drf-spectacular` (OpenAPI schema + Swagger UI)          |
| Media storage        | Direct-to-S3 presigned uploads (`boto3`) + CloudFront signed delivery (`cryptography`) |
| Email                 | Console backend in dev, SMTP in production               |
| Tests                | `pytest` + `pytest-django`                               |

## Project layout

```
config/
  settings/
    base.py          # shared settings, env-driven
    development.py    # DEBUG=True overrides
    production.py     # secure-cookie / HSTS / SMTP overrides, refuses to boot with
                       # CELERY_TASK_ALWAYS_EAGER=true
  urls.py             # root URL routing (mounts each app under /api/...)
  asgi.py             # Channels ProtocolTypeRouter (http + websocket)
  wsgi.py
  celery.py           # Celery app, autodiscovers apps/*/tasks.py
apps/
  users/              # auth: register, OTP verify/resend, login, refresh, logout, delete
  profiles/           # profile, profile photo gallery, privacy settings, preferences
  verifications/       # identity verification submission + admin review/update queue
  matches/            # suggestions, filtered search, match requests
  chat/               # WebSocket chat consumer + REST message history
  gallery/             # personal photo gallery, shared with accepted matches via explicit grants
  subscriptions/       # subscription plans + payment status
  reviews/            # public app reviews
  reports/            # user-to-user abuse reports
core/                 # cross-app helpers: pagination, throttles, permissions,
                       # exception handling, validators, utils, media storage/upload
                       # helpers (presigned S3 posts, CloudFront signing)
requirements/
  base.txt            # shared dependencies
  development.txt     # base + pytest
  production.txt      # base + gunicorn/uvicorn
```

## Local setup

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:
   ```
   pip install -r requirements/development.txt
   ```
3. Copy `.env.example` to `.env` and adjust the values (see [Environment
   variables](#environment-variables) below).
4. Make sure Redis is running and reachable at `REDIS_HOST:REDIS_PORT`
   (Redis backs the cache, Celery broker/result backend, and the Channels
   layer — it is required even for local development).
5. Run migrations:
   ```
   python manage.py migrate
   ```
6. Start the services, each in its own terminal:
   ```
   python manage.py runserver
   celery -A config worker -l info -Q critical,default,media,batch
   celery -A config beat -l info
   ```

By default (no `POSTGRES_DB` set) the app falls back to a local `db.sqlite3`
file. Set the `POSTGRES_*` variables to use PostgreSQL instead.

There is no local/filesystem fallback for media: photo uploads always go
through a presigned S3 POST, so exercising the photo/gallery endpoints
locally requires a real (or dev-only) S3 bucket configured via the
`AWS_*`/`CLOUDFRONT_*` variables below. AWS credentials themselves come from
the standard AWS SDK chain (env vars, shared config, or an IAM role), not
from Django settings.

### Running tests

```
pytest
```

`pytest.ini` points `DJANGO_SETTINGS_MODULE` at `config.settings.base`, so no
extra environment variables are needed to run the suite.

## Environment variables

All variables are read via `os.getenv` / `python-decouple` in
`config/settings/base.py`, with sensible development defaults.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev-only placeholder | Django secret key — must be overridden in production |
| `DJANGO_DEBUG` | `true` | Toggles debug mode; `development.py` forces it `True`, `production.py` forces it `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `TIME_ZONE` | `Asia/Karachi` | Django `TIME_ZONE` |
| `CORS_ALLOWED_ORIGINS` | *(empty)* | Comma-separated origins allowed by `django-cors-headers` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` / `POSTGRES_PORT` | *(unset → SQLite)* | PostgreSQL connection; setting `POSTGRES_DB` switches the DB engine on |
| `DB_CONN_MAX_AGE` | `0` | Django DB connection lifetime; kept at `0` because the app expects Postgres behind PgBouncer in transaction-pooling mode |
| `DB_DISABLE_SERVER_SIDE_CURSORS` | `true` | Must stay `true` under transaction-mode pooling (a server-side cursor can outlive the pooled connection it opened on) |
| `REDIS_HOST` / `REDIS_PORT` | `127.0.0.1` / `6379` | Local-dev fallback Redis connection, used to derive the cache/Celery/Channels URLs below when they aren't set explicitly |
| `REDIS_CACHE_URL` | derived from `REDIS_HOST`/`PORT`, db `0` | Redis used by the Django cache and DRF throttling |
| `REDIS_CELERY_URL` | derived from `REDIS_HOST`/`PORT`, db `1` | Redis used as the Celery broker/result backend — should be a separate instance in production |
| `REDIS_CHANNELS_URL` | derived from `REDIS_HOST`/`PORT`, db `2` | Redis used by the Channels layer |
| `CHANNELS_LAYER_CAPACITY` | `300` | Max buffered messages per channel-layer group before backpressure |
| `CHANNELS_LAYER_EXPIRY` | `60` | Seconds before a buffered channel-layer message expires |
| `CELERY_TASK_ALWAYS_EAGER` | follows `DJANGO_DEBUG` | Run Celery tasks synchronously; `production.py` refuses to start if this is `true` |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` | Keeps a slow worker from hoarding tasks it can't get to promptly |
| `CELERY_VISIBILITY_TIMEOUT_SECONDS` | `3600` | Must exceed the slowest task's runtime, or the broker redelivers a still-running task |
| `EMAIL_BACKEND` | console backend | Set to the SMTP backend in production |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_USE_TLS` / `EMAIL_USE_SSL` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | — | SMTP credentials, used when `EMAIL_BACKEND` is the SMTP backend |
| `DEFAULT_FROM_EMAIL` | `Muslim Matrimonial <no-reply@muslimmatrimonial.local>` | From address for OTP and notification emails |
| `EMAIL_TIMEOUT` | `10` | SMTP send timeout (seconds) |
| `AWS_STORAGE_BUCKET_NAME` | *(empty)* | Private S3 bucket that backs every photo upload |
| `AWS_S3_REGION_NAME` | `us-east-1` | Region of that bucket |
| `AWS_S3_QUARANTINE_PREFIX` | `quarantine` | Key prefix newly-uploaded, not-yet-validated photos are written under |
| `CLOUDFRONT_DOMAIN` / `CLOUDFRONT_KEY_PAIR_ID` / `CLOUDFRONT_PRIVATE_KEY` | *(empty)* | CloudFront signed-URL delivery; required in production (the bucket has no public access), falls back to a signed S3 GET URL when unset |
| `MEDIA_UPLOAD_MAX_BYTES` | `2097152` (2MB) | Max size enforced by the presigned POST policy |
| `MEDIA_UPLOAD_URL_TTL_SECONDS` | `300` | How long a presigned upload POST stays valid |
| `MEDIA_SIGNED_URL_TTL_SECONDS` | `300` | How long a signed delivery URL stays valid |
| `MEDIA_QUARANTINE_EXPIRY_HOURS` | `24` | How long an unfinalized/failed upload is kept before the sweep task removes it |

Switch settings modules with `DJANGO_SETTINGS_MODULE`:
`config.settings.development` for local work, `config.settings.production`
for deployment (adds HSTS, secure cookies, and SSL-proxy header handling).

## Authentication flow

1. `POST /api/auth/register` — creates an inactive user and emails a 6-digit
   OTP (also returned in the response body when `DEBUG=True`).
2. `POST /api/auth/verify-otp` — verifies the OTP and activates the account.
3. `POST /api/auth/resend-otp` — re-sends the OTP for an unverified account
   (rejects already-verified emails); rate-limited by the same `otp_email`
   throttle as registration.
4. `POST /api/auth/login` — returns `{ access, refresh, user }`.
5. `POST /api/auth/refresh-token` — exchanges a refresh token for a new
   access token (`rest_framework_simplejwt.views.TokenRefreshView`; refresh
   token rotation is off by default, so only `access` comes back).
6. `POST /api/auth/logout` — blacklists the given refresh token.
7. `POST /api/auth/forgot-password` — called twice: once with just `email` to
   request an OTP, again with `email` + `otp` + `new_password` to reset it.
8. `DELETE /api/auth/delete` — soft-deletes the authenticated account
   (`status=deleted`, `is_active=False`, keeps the row for audit purposes).

Access tokens last 30 minutes, refresh tokens last 30 days
(`SIMPLE_JWT` in `config/settings/base.py`). All authenticated requests use
`Authorization: Bearer <access_token>`.

An `insomnia_collection.json` is included at the repo root with every
endpoint pre-built; its Login and Refresh Token requests have an
after-response script that writes `access_token` / `refresh_token` into the
Insomnia base environment automatically.

## API overview

All routes are mounted under `/api/` in `config/urls.py`.

| Prefix | App | Notes |
|---|---|---|
| `/api/auth/` | `apps.users` | Registration, OTP verify/resend, login/refresh/logout, forgot password, account deletion |
| `/api/profile/` | `apps.profiles` | Profile CRUD, two-step presigned photo upload (max 6 photos, 2MB each, JPEG/PNG/WEBP), privacy settings, partner preferences |
| `/api/verifications/` | `apps.verifications` | Submit identity verification (faith declaration, document URL); `admin/pending` (filterable/paginated) and `admin/<pk>` (`PATCH`) for staff review |
| `/api/admin/verifications/pending` | `apps.verifications` | Same staff-only pending queue, mounted directly at the root for convenience |
| `/api/matches/` | `apps.matches` | Daily suggestions, filtered search, send/respond to match requests |
| `/api/chat/` | `apps.chat` | REST message history per match; live messaging is over WebSocket |
| `/api/gallery/` | `apps.gallery` | Personal photo gallery (two-step presigned upload, max 6 photos), shared with a match only after an explicit access grant |
| `/api/subscriptions/` | `apps.subscriptions` | Plan list/create, current status, payment status updates |
| `/api/reviews/` | `apps.reviews` | Public reviews are readable by anyone; creation requires auth, deletion is admin-only |
| `/api/reports/` | `apps.reports` | Authenticated users report other accounts |
| `/api/schema/`, `/api/docs/` | `drf-spectacular` | OpenAPI schema and Swagger UI |

### Profile discovery rule

Users must create both a `Profile` and a `Preference`. Suggestions and
filtered results are **reciprocal**: the viewer must be interested in the
candidate's gender, the candidate must be interested in the viewer's gender,
and each user's saved age/location/education/sect filters must admit the
other. The same rule protects direct profile access and match-request
creation (`apps/matches/services.py`).

### Photo uploads

Both profile photos (`apps.profiles`) and personal gallery photos
(`apps.gallery`) use the same two-step, direct-to-S3 flow
(`core/media_uploads.py`, `core/media_storage.py`):

1. `POST .../upload` (or `.../photos/upload`) reserves a gallery slot and
   returns a presigned S3 `POST` (url + fields). The slot count check and
   reservation happen atomically under a row lock on the user, so two
   concurrent presign requests can't both squeeze past the 6-photo cap.
2. The client uploads the file bytes directly to S3 with those fields — the
   bytes never pass through Django.
3. `POST .../<pk>/finalize` confirms the object landed in S3, then queues a
   Celery task (`validate_and_promote_photo` / `validate_and_promote_personal_photo`)
   that checks the file signature, decodes it, strips EXIF metadata,
   re-encodes it to WEBP, and promotes it out of the quarantine prefix.

Uploads that are never finalized (or fail validation) are removed by hourly
sweep tasks (`sweep_abandoned_photo_uploads`, `sweep_abandoned_personal_photo_uploads`).
All photo reads go through short-lived signed delivery URLs
(`media_storage.signed_delivery_url`) — CloudFront when configured, a signed
S3 GET URL otherwise — minted only after the caller's own authorization
check; the bucket itself has no public access path.

### Photo privacy

Each profile photo has a `privacy_level` (`visible`, `blur_till_match`,
`always_blur`), falling back to the profile's default. `blur_till_match`
photos are only revealed to the profile owner, staff, or a user with an
`accepted` `MatchRequest` between the two profiles; everyone else gets
`url: null, is_blurred: true`.

Personal gallery photos (`apps.gallery`) are private by default and only
become visible to another user once the owner explicitly grants access for
an accepted match (`GalleryAccess`); there is no privacy-level system there,
just an allow-list per match.

### Real-time chat

WebSocket endpoint: `ws://<host>/ws/chat/<match_id>?token=<jwt-access-token>`

- Authenticated via `apps/chat/middleware.py`'s `JWTAuthMiddleware`, which
  decodes the `token` query param into `scope["user"]`.
- Only participants of an `accepted` match may connect (enforced in
  `apps/chat/consumers.py`).
- `GET /api/chat/<match_id>/history` returns the persisted message history
  over REST for the same match.

### Rate limiting

Configured in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`
(`config/settings/base.py`) and applied per-view via custom throttle classes
in `core/throttles.py` (IP-based for anonymous, user-based for
authenticated):

| Scope | Rate | Applies to |
|---|---|---|
| `otp_email` | 4/hour | Register, resend-OTP, forgot-password OTP emails, keyed by email |
| `auth` | 5/hour | Register, login, forgot-password |
| `auth_authenticated` | 50/hour | OTP verification |
| `profile` | 50/hour | Profile endpoints, including profile photo upload/finalize |
| `match` | 50/hour | Suggestions, filter, match requests |
| `chat` | 50/minute | Chat endpoints |

### Roles and account status

`User.role` is one of `user`, `matchmaker`, `admin`; `User.status` is one of
`active`, `suspended`, `deleted`. Login requires `otp_verified=True`,
`is_active=True`, and `status="active"`. Admin-only endpoints (verification
review, review deletion, subscription payment-status updates) are gated by
`core/permissions.py`'s `IsAdminRole`.

## Admin

Django admin is available at `/admin/` (uses the default, unstyled
`django.contrib.admin` theme — no custom theme is installed yet).

## Background jobs

Celery workers are expected to run against four dedicated queues —
`critical`, `default`, `media`, `batch` — so a burst of media-validation or
batch work can never delay time-sensitive OTP email delivery
(`CELERY_TASK_ROUTES` in `config/settings/base.py`). Tasks are acknowledged
late and redelivered on worker loss (`CELERY_TASK_ACKS_LATE`,
`CELERY_TASK_REJECT_ON_WORKER_LOST`), with a prefetch multiplier of 1 so a
slow worker doesn't hoard tasks.

Celery Beat schedules:
- `apps.matches.tasks.build_daily_suggestions` — every 24 hours, precomputes
  match suggestions (`batch` queue).
- `apps.profiles.tasks.sweep_abandoned_photo_uploads` /
  `apps.gallery.tasks.sweep_abandoned_personal_photo_uploads` — hourly,
  clean up quarantined uploads that were never finalized or failed
  validation (`batch` queue).

OTP emails are sent asynchronously via `apps.users.tasks.send_otp` on the
`critical` queue, with up to 3 retries on send failure; the OTP value itself
is generated synchronously so it's available immediately for tests/`DEBUG`
responses even if the email task is delayed. Photo validation
(`validate_and_promote_photo`, `validate_and_promote_personal_photo`) and
object deletion run on the `media` queue.
