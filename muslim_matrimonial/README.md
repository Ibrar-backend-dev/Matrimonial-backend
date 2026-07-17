# Muslim Matrimonial Backend

Django REST Framework backend with JWT authentication, reciprocal profile discovery,
verification, matching, real-time chat, subscriptions, reviews, and reports.

## Local setup

1. Create and activate a Python 3.12 virtual environment.
2. Install `requirements/development.txt`.
3. Copy `.env.example` to `.env` and adjust the values.
4. Run `python manage.py migrate`.
5. Start Redis, then run Django, a Celery worker, and Celery beat.

API documentation is served at `/api/docs/`. WebSocket chat uses
`/ws/chat/<match-id>?token=<jwt-access-token>` and only permits participants of an
accepted match.

## Profile discovery rule

Users must create both a profile and a preference. Suggestions and filtered results
are reciprocal: the viewer must be interested in the candidate's gender, the candidate
must be interested in the viewer's gender, and each user's saved age/location/education/
sect filters must admit the other. The same rule protects direct profile access and
match-request creation.
