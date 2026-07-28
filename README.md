# Muslim Matrimonial Backend

A Django REST Framework backend for a Muslim matrimonial platform: JWT-based
authentication with email OTP verification, profile management with privacy-aware
photo galleries, reciprocal match discovery, real-time chat over WebSockets,
subscriptions, reviews, and abuse reports.

## Tech stack

| Concern             | Technology                                              |
|----------------------|----------------------------------------------------------|
| Framework            | Django 5.0, Django REST Framework 3.15                  |
| Auth                 | `djangorestframework-simplejwt` (access + refresh tokens) |
| Real-time            | Django Channels 4 + `channels-redis` (ASGI, WebSockets)  |
| Background jobs      | Celery 5 + Celery Beat, Redis as broker/result backend   |
| Database             | PostgreSQL (via `psycopg2`) in production, SQLite for local dev fallback |
| Caching / throttling | Redis-backed Django cache (`django-redis`), local memory cache in dev |
| API docs             | `drf-spectacular` (OpenAPI schema + Swagger UI)          |
| Media storage        | `django-storages` + `boto3` (S3-compatible, optional)    |
| Email                 | Console backend in dev, SMTP in production               |
| Tests                | `pytest` + `pytest-django`                               |

## Project layout

```
config/
  settings/
    base.py          # shared settings, env-driven
    development.py    # DEBUG=True overrides
    production.py     # secure-cookie / HSTS / SMTP overrides
  urls.py             # root URL routing (mounts each app under /api/...)
  asgi.py             # Channels ProtocolTypeRouter (http + websocket)
  wsgi.py
  celery.py           # Celery app, autodiscovers apps/*/tasks.py
apps/
  users/              # auth: register, OTP verify, login, refresh, logout, delete
  profiles/           # profile, photo gallery, privacy settings, preferences
  verifications/       # identity verification submission + admin review queue
  matches/            # suggestions, filtered search, match requests
  chat/               # WebSocket chat consumer + REST message history
  subscriptions/       # subscription plans + payment status
  reviews/            # public app reviews
  reports/            # user-to-user abuse reports
core/                 # cross-app helpers: pagination, throttles, permissions,
                       # exception handling, validators, utils
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
   celery -A config worker -l info
   celery -A config beat -l info
   ```

By default (no `POSTGRES_DB` set) the app falls back to a local `db.sqlite3`
file. Set the `POSTGRES_*` variables to use PostgreSQL instead.

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
| `REDIS_HOST` / `REDIS_PORT` | `127.0.0.1` / `6379` | Redis connection used for Celery broker/backend and the Channels layer |
| `CELERY_TASK_ALWAYS_EAGER` | follows `DJANGO_DEBUG` | Run Celery tasks synchronously (useful without a running worker) |
| `EMAIL_BACKEND` | console backend | Set to the SMTP backend in production |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_USE_TLS` / `EMAIL_USE_SSL` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | — | SMTP credentials, used when `EMAIL_BACKEND` is the SMTP backend |
| `DEFAULT_FROM_EMAIL` | `Muslim Matrimonial <no-reply@muslimmatrimonial.local>` | From address for OTP and notification emails |
| `EMAIL_TIMEOUT` | `10` | SMTP send timeout (seconds) |

Switch settings modules with `DJANGO_SETTINGS_MODULE`:
`config.settings.development` for local work, `config.settings.production`
for deployment (adds HSTS, secure cookies, and SSL-proxy header handling).

## Authentication flow

1. `POST /api/auth/register` — creates an inactive user and emails a 6-digit
   OTP (also returned in the response body when `DEBUG=True`).
2. `POST /api/auth/verify-otp` — verifies the OTP and activates the account.
3. `POST /api/auth/login` — returns `{ access, refresh, user }`.
4. `POST /api/auth/refresh-token` — exchanges a refresh token for a new
   access token (`rest_framework_simplejwt.views.TokenRefreshView`; refresh
   token rotation is off by default, so only `access` comes back).
5. `POST /api/auth/logout` — blacklists the given refresh token.
6. `POST /api/auth/forgot-password` — called twice: once with just `email` to
   request an OTP, again with `email` + `otp` + `new_password` to reset it.
7. `DELETE /api/auth/delete` — soft-deletes the authenticated account
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
| `/api/auth/` | `apps.users` | Registration, OTP, login/refresh/logout, forgot password, account deletion |
| `/api/profile/` | `apps.profiles` | Profile CRUD, photo gallery (max 6 photos, 2MB each, JPEG/PNG/WEBP), privacy settings, partner preferences |
| `/api/verifications/` | `apps.verifications` | Submit identity verification (faith declaration, document URL) |
| `/api/admin/verifications/pending` | `apps.verifications` | Staff-only queue of pending verifications |
| `/api/matches/` | `apps.matches` | Daily suggestions, filtered search, send/respond to match requests |
| `/api/chat/` | `apps.chat` | REST message history per match; live messaging is over WebSocket |
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

### Photo privacy

Each photo has a `privacy_level` (`visible`, `blur_till_match`,
`always_blur`), falling back to the profile's default. `blur_till_match`
photos are only revealed to the profile owner, staff, or a user with an
`accepted` `MatchRequest` between the two profiles; everyone else gets
`url: null, is_blurred: true`.

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
| `otp_email` | 4/hour | Register / forgot-password OTP emails, keyed by email |
| `auth` | 2/hour | Register, login, forgot-password |
| `auth_authenticated` | 20/hour | OTP verification |
| `profile` | 20/hour | Profile endpoints |
| `match` | 50/hour | Suggestions, filter, match requests |
| `chat` | 50/minute | Chat endpoints |

### Roles and account status

`User.role` is one of `user`, `matchmaker`, `admin`; `User.status` is one of
`active`, `suspended`, `deleted`. Login requires `otp_verified=True`,
`is_active=True`, and `status="active"`.

## Admin

Django admin is available at `/admin/` (uses the default, unstyled
`django.contrib.admin` theme — no custom theme is installed yet).

## Background jobs

Celery Beat runs `apps.matches.tasks.build_daily_suggestions` once every 24
hours to precompute match suggestions. OTP emails are sent asynchronously via
`apps.users.tasks.send_otp`, with up to 3 retries on send failure; the OTP
value itself is generated synchronously so it's available immediately for
tests/`DEBUG` responses even if the email task is delayed.
