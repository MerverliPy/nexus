"""MinIO storage utilities for receipt images."""

import io
from datetime import timedelta
from pathlib import Path
from typing import Optional

from minio import Minio
from minio.error import S3Error

# MinIO configuration
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
RECEIPTS_BUCKET = "receipts"
PUBLIC_BUCKET = "public"


def _get_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def ensure_buckets() -> None:
    """Create required buckets if they don't exist."""
    client = _get_client()
    for bucket in [RECEIPTS_BUCKET, PUBLIC_BUCKET]:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)


def upload_receipt(file_path: str | Path, object_name: Optional[str] = None) -> str:
    """Upload a receipt image to MinIO and return the URL.

    Returns a presigned URL for viewing.
    """
    ensure_buckets()
    client = _get_client()
    file_path = Path(file_path)

    if object_name is None:
        object_name = file_path.name

    # Upload
    client.fput_object(RECEIPTS_BUCKET, object_name, str(file_path))

    # Generate presigned URL (7 days expiry)
    url = client.presigned_get_object(
        RECEIPTS_BUCKET,
        object_name,
        expires=timedelta(days=7),
    )
    return url


def upload_receipt_bytes(data: bytes, object_name: str) -> str:
    """Upload receipt image bytes to MinIO and return presigned URL."""
    ensure_buckets()
    client = _get_client()
    file_size = len(data)

    client.put_object(
        RECEIPTS_BUCKET,
        object_name,
        io.BytesIO(data),
        file_size,
        content_type="image/jpeg",
    )

    url = client.presigned_get_object(
        RECEIPTS_BUCKET,
        object_name,
        expires=timedelta(days=7),
    )
    return url
