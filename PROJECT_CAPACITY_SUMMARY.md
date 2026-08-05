# Project Capacity Summary and Improvement Plan

## Overview
This document records the current architecture improvements, app-specific behavior, concurrency estimates, and next-step implementation plan for the Muslim Matrimonial backend.

The project uses:
- Django 5 + Django REST Framework
- Django Channels + Redis for WebSocket chat
- Celery + Redis for background task processing
- PostgreSQL in production, SQLite fallback in development
- JWT authentication with refresh/blacklist support
- Presigned direct-to-S3 upload flow for media

---

## Validated improvement list

### apps/users
- Responsibilities: register, OTP verify, login, refresh, logout, forgot password, delete.
- Confirmed improvements:
  - OTP/email throttling is implemented in `apps/users/views.py` via `OTPEmailRateThrottle`.
  - `RegisterView`, `ResendOTPView`, and `ForgotPasswordView` are protected by OTP throttling.
  - JWT refresh is provided by `RefreshTokenView = TokenRefreshView`.
  - Logout blacklists refresh tokens in `LogoutView`.
- Protection and capacity:
  - Rate limits in `config/settings/base.py`:
    - `otp_email`: `4/hour`
    - `auth`: `5/hour`
    - `auth_authenticated`: `50/hour`
  - These limits bound auth-related bursts and protect the system from credential abuse.

### apps/profiles
- Responsibilities: profile CRUD, photo gallery, privacy settings, partner preferences.
- Confirmed improvements:
  - Direct S3 upload request and finalize flow in `apps/profiles/views.py`.
  - `reserve_upload_slot()` in `core/media_uploads.py` uses `select_for_update()` on the `User` row to avoid concurrent gallery slot races.
  - Async validation is queued through Celery tasks such as `validate_and_promote_photo`.
  - Privacy controls are enforced in profile retrieval and photo visibility logic.
- Protection and capacity:
  - `profile` throttle is `50/hour` per authenticated user.
  - This bounds write-heavy profile and photo operations while allowing reads to scale.

### apps/verifications
- Responsibilities: identity verification submission, pending verification admin list.
- Confirmed improvements:
  - User verification submission via `VerificationSubmitView`.
  - Admin pending-verification endpoint via `PendingVerificationListView`.
  - Admin update endpoint via `AdminVerificationUpdateView`.
  - Admin endpoints are protected by `IsAdminRole`.
- Behavior:
  - Low-volume verification submission workload.
  - Admin list reads pending users and is optimized for staff review.
  - Admins can update verification status and `verified_by` metadata through `PATCH /api/verifications/admin/<pk>`.

### apps/matches
- Responsibilities: suggestions, filtered match search, send/respond to match requests.
- Confirmed improvements:
  - Daily suggestion caching in `apps/matches/services.py` via `get_daily_suggestions()`.
  - Reciprocal eligibility enforcement in `eligible_profiles()`.
- Protection and capacity:
  - `match` throttle is `50/hour` per authenticated user.
  - This limits repeated match actions and reduces query pressure.
  - Cached suggestion IDs reduce repeated full query cost.

### apps/chat
- Responsibilities: real-time chat over WebSocket, REST history retrieval.
- Confirmed improvements:
  - WebSocket JWT auth in `apps/chat/middleware.py`.
  - Match membership and accepted-match verification in `ChatConsumer.connect()`.
  - Message rate limit: `20` messages per `10` seconds` in `ChatConsumer.check_rate_limit()`.
  - Missed-message recovery via `after` query parameter and `missed_messages()`.
  - Channel layer capacity is set to `300` in `config/settings/base.py`.
- Behavior:
  - The chat subsystem is designed for authenticated real-time messaging with spam control.
  - WebSocket scaling is bounded by channel layer capacity and ASGI worker count.

### apps/subscriptions, apps/reviews, apps/reports
- Responsibilities:
  - `apps/subscriptions`: user subscription CRUD, current subscription lookup, admin payment status patch.
  - `apps/reviews`: public review listing, authenticated review creation, admin delete.
  - `apps/reports`: authenticated abuse report CRUD.
- Confirmed behavior:
  - These apps use standard transactional and CRUD flows.
  - They are lower throughput than core auth/profile/match/chat flows.
  - No special throttling is currently applied in the view code.

### apps/gallery
- Responsibilities: personal photo uploads, shared galleries, access grants.
- Confirmed improvements:
  - Direct S3 upload reservation in `OwnPhotoUploadRequestView`.
  - `OwnPhotoFinalizeView` queues validation via Celery task `validate_and_promote_personal_photo`.
  - Shared-gallery access is enforced only between accepted matches and explicit gallery grants.
- Behavior:
  - Binary media bytes bypass the app server, reducing app CPU and memory load.
  - Server-side processing is offloaded to Celery, improving concurrency for upload flows.

---

## Admin verification API
- The admin verification API already exists:
  - `POST /api/verifications/` for user verification submission.
  - `GET /api/admin/verificats/pending` for staff/admin review.
- Admin access is enforced by `IsAdminRole` in `apps/verifications/views.py`.

---

## Hardware-specific guidance: 4 cores, 12 GB RAM
On a single 4-core / 12 GB machine, the app is suitable for small-to-moderate production or staging workloads.

Suggested allocation:
- 2–3 ASGI workers for HTTP and WebSocket traffic.
- 1–2 Celery workers for background task processing.
- External Redis is preferred; if Redis is local, reserve 2–3 GB RAM for it.
- Keep Postgres connection pooling modest (e.g. 6–10 client connections) on this machine.

Expected capacity by app:
- `apps/users`: hundreds of concurrent auth sessions, with auth flow bursts limited by throttles.
- `apps/profiles`: dozens to low hundreds of concurrent reads, 20–40 concurrent writes.
- `apps/matches`: 40–80 concurrent browse/search users, 20–30 concurrent request actions.
- `apps/chat`: 150–250 concurrent WebSocket chat connections, depending on idle/active ratio.
- `apps/subscriptions`, `apps/reviews`, `apps/reports`: dozens to low hundreds of concurrent users.
- `apps/gallery`: 50–100 concurrent upload-related operations; actual byte upload work bypasses the app.

---

## Proposed improvement plan

### apps/users
- Add explicit login failure counters or account lockout after repeated bad credentials.
- Add monitoring for OTP delivery and refresh/logout events.
- Document auth throttling policies clearly in the API docs.

### apps/profiles
- Add explicit database indexes for profile filtering fields used by reciprocal matching.
- Add throttled profile browsing if reads become heavy.
- Expose visibility rules in API docs.

### apps/verifications
- Add pagination and filtering to pending verification list.
- Add notifications or status update endpoints for verification results.

### apps/matches
- Add indexes for match query fields such as `Profile.gender`, `user__preference__interested_in`, age ranges, city, education, sect.
- Add cache invalidation on preference/profile changes.
- Add metrics for match request volume and cache hit rate.

### apps/chat
- Add metrics for active WebSocket connections and chat group size.
- Add configurable connection throttling for reconnect storms.
- Add per-match group limits if a chat becomes too large.

### apps/subscriptions / apps/reviews / apps/reports
- Add optional create throttles for spam-prone actions.
- Add review/report moderation dashboards or alerting.

### apps/gallery
- Add upload status polling endpoint for validation progress.
- Harden abandoned upload cleanup and S3 quarantine expiration.
- Add audit logs for gallery access grants.

---

## Next step
If desired, the next step is to implement the highest-value improvements from the proposed plan, starting with:
1. DB indexes for match/profile filtering.
2. admin pagination/filtering for verifications.
3. metrics for chat connections and throttling.
4. an API endpoint for upload validation status.
