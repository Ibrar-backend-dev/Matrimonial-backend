FROM python:3.12-slim

# DJANGO_SETTINGS_MODULE: every entrypoint (manage.py, config/asgi.py,
# config/wsgi.py, config/celery.py) only os.environ.setdefault()s this to
# config.settings.base, so without it here a deploy silently boots the
# development settings -- DEBUG=True, the hardcoded dev SECRET_KEY, no HSTS and
# no secure cookies. Baking it into the image means it can't be forgotten; a
# Railway service variable still overrides it.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

# Keep the repo-root/project-subfolder nesting from the source tree so
# BASE_DIR.parent (config/settings/base.py) still resolves to /app/media --
# flattening this into /app would silently repoint MEDIA_ROOT to /media.
WORKDIR /app/muslim_matrimonial

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY muslim_matrimonial/requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/production.txt

COPY muslim_matrimonial/ .

EXPOSE 8000

# collectstatic and migrate need real DB/secret env vars, which only exist at
# container runtime on Railway (not at `docker build` time), so they run from
# each service's start command (see railway*.json) instead of here.
CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
