from contextlib import contextmanager

from django.core.cache import cache


@contextmanager
def distributed_lock(name, timeout=300, blocking_timeout=5):
    """Redis-backed distributed lock (via django-redis) for scheduled tasks that
    must not run concurrently -- e.g. Celery Beat briefly running two instances
    during a deploy. Pass blocking_timeout=0 for "skip if already running"
    semantics instead of waiting; raises RuntimeError if the lock isn't
    acquired within blocking_timeout.
    """
    lock = cache.lock(f"lock:{name}", timeout=timeout, blocking_timeout=blocking_timeout)
    if not lock.acquire(blocking=True):
        raise RuntimeError(f"Could not acquire lock '{name}' within {blocking_timeout}s")
    try:
        yield
    finally:
        lock.release()
