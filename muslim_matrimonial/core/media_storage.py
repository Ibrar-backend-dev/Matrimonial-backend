import datetime
import logging
import uuid
from pathlib import Path

import boto3
from django.conf import settings

logger = logging.getLogger(__name__)

_EXTENSION_BY_CONTENT_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _local_path(key):
    path = Path(settings.MEDIA_ROOT) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _using_s3():
    return bool(settings.AWS_STORAGE_BUCKET_NAME)


def extension_for(content_type):
    return _EXTENSION_BY_CONTENT_TYPE.get(content_type, "bin")


def _s3_client():
    if not _using_s3():
        raise RuntimeError("AWS_STORAGE_BUCKET_NAME is not configured.")
    return boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)


def quarantine_key(prefix, owner_id, content_type):
    return f"{settings.AWS_S3_QUARANTINE_PREFIX}/{prefix}/{owner_id}/{uuid.uuid4()}.{extension_for(content_type)}"


def serving_key(prefix, owner_id):
    # Always WEBP -- validate_and_normalize() re-encodes every accepted
    # upload to WEBP as part of stripping metadata, regardless of the
    # original format.
    return f"{prefix}/{owner_id}/{uuid.uuid4()}.webp"


def create_presigned_post(key, content_type, max_bytes):
    """Presigned S3 POST (not PUT) -- POST policy conditions are what let us
    enforce content-type and a size ceiling at the presigning layer itself,
    before any bytes reach S3.
    """
    if not _using_s3():
        raise RuntimeError("S3 uploads are disabled because AWS_STORAGE_BUCKET_NAME is not configured.")
    client = _s3_client()
    return client.generate_presigned_post(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, max_bytes],
        ],
        ExpiresIn=settings.MEDIA_UPLOAD_URL_TTL_SECONDS,
    )


def head_object(key):
    if _using_s3():
        client = _s3_client()
        try:
            response = client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        except client.exceptions.ClientError:
            return None
        return {"size": response["ContentLength"], "content_type": response.get("ContentType")}

    path = _local_path(key)
    if not path.exists():
        return None
    return {"size": path.stat().st_size, "content_type": None}


def get_object_bytes(key):
    if _using_s3():
        client = _s3_client()
        response = client.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        return response["Body"].read()

    return _local_path(key).read_bytes()


def put_object_bytes(key, data, content_type):
    if _using_s3():
        client = _s3_client()
        client.put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key, Body=data, ContentType=content_type)
        return

    _local_path(key).write_bytes(data)


def delete_object(key):
    if not key:
        return
    if _using_s3():
        client = _s3_client()
        try:
            client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        except Exception:
            logger.exception("Failed to delete S3 object %s", key)
        return

    path = _local_path(key)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        logger.exception("Failed to delete local media object %s", key)


def signed_delivery_url(key, expires_in=None):
    """Signed URL for private media -- callers must only invoke this after
    their own authorization check (privacy_level / match / gallery-access
    rules); this function itself has no authorization concept, it only signs.

    Uses CloudFront signed URLs when CLOUDFRONT_* is configured (the real
    production path -- the bucket has no public access at all). Falls back to
    a signed S3 GET URL when CloudFront isn't configured (local/dev without a
    CloudFront distribution provisioned yet).
    """
    if not key:
        return None
    expires_in = expires_in or settings.MEDIA_SIGNED_URL_TTL_SECONDS
    if settings.CLOUDFRONT_DOMAIN and settings.CLOUDFRONT_KEY_PAIR_ID and settings.CLOUDFRONT_PRIVATE_KEY:
        return _cloudfront_signed_url(key, expires_in)
    if _using_s3():
        client = _s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
    return f"{settings.MEDIA_URL.rstrip('/')}/{key}"


def _cloudfront_signed_url(key, expires_in):
    from botocore.signers import CloudFrontSigner
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key = load_pem_private_key(settings.CLOUDFRONT_PRIVATE_KEY.encode(), password=None)

    def rsa_signer(message):
        return private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())

    signer = CloudFrontSigner(settings.CLOUDFRONT_KEY_PAIR_ID, rsa_signer)
    url = f"https://{settings.CLOUDFRONT_DOMAIN}/{key}"
    expire_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    return signer.generate_presigned_url(url, date_less_than=expire_at)
