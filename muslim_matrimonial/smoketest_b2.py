#!/usr/bin/env python
"""Connectivity smoke test for the configured media storage backend (S3/B2).

Exercises core.media_storage end-to-end against the real bucket: uploads a
throwaway object, HEADs it, downloads it back, then deletes it and confirms
it's gone. Run this after dropping real credentials into .env to confirm the
B2 (or S3) connection actually works before wiring it into the app.

Run from this directory (same place as manage.py):
    python smoketest_b2.py
"""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

import django

django.setup()

from django.conf import settings

from core.media_storage import delete_object, get_object_bytes, head_object, put_object_bytes


def main():
    if not settings.AWS_STORAGE_BUCKET_NAME:
        print("AWS_STORAGE_BUCKET_NAME is not set -- storage falls back to local MEDIA_ROOT, nothing to test.")
        sys.exit(1)

    key = f"{settings.AWS_S3_QUARANTINE_PREFIX}/smoketest/{uuid.uuid4()}.txt"
    payload = b"muslim_matrimonial storage smoketest"

    print(f"Bucket:   {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"Region:   {settings.AWS_S3_REGION_NAME}")
    print(f"Endpoint: {settings.AWS_S3_ENDPOINT_URL or '(default AWS)'}")
    print(f"Key:      {key}")

    print("\n[1/4] put_object_bytes ...")
    put_object_bytes(key, payload, "text/plain")
    print("      OK")

    print("[2/4] head_object ...")
    meta = head_object(key)
    if meta is None:
        raise RuntimeError("head_object returned None right after upload -- object not visible.")
    if meta["size"] != len(payload):
        raise RuntimeError(f"size mismatch: expected {len(payload)}, got {meta['size']}")
    print(f"      OK ({meta})")

    print("[3/4] get_object_bytes ...")
    fetched = get_object_bytes(key)
    if fetched != payload:
        raise RuntimeError("downloaded bytes do not match what was uploaded.")
    print("      OK (bytes match)")

    print("[4/4] delete_object ...")
    delete_object(key)
    if head_object(key) is not None:
        raise RuntimeError("object still exists after delete_object.")
    print("      OK (confirmed gone)")

    print("\nAll checks passed -- storage connection is working end-to-end.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nFAILED: {exc}")
        sys.exit(1)
