"""Tests for MinIO storage utilities — bucket management, file upload, presigned URLs.

All tests mock the Minio client to avoid needing a running MinIO server.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nexus.utils.storage import (
    RECEIPTS_BUCKET,
    PUBLIC_BUCKET,
    _get_client,
    ensure_buckets,
    upload_receipt,
    upload_receipt_bytes,
)


# ── _get_client ──────────────────────────────────────────────────────────────


@patch("nexus.utils.storage.Minio")
def test_get_client_creates_minio_instance(mock_minio):
    mock_minio.return_value = MagicMock()
    client = _get_client()
    assert client is mock_minio.return_value
    mock_minio.assert_called_once_with(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False,
    )


# ── ensure_buckets ───────────────────────────────────────────────────────────


@patch("nexus.utils.storage.Minio")
def test_ensure_buckets_creates_missing_buckets(mock_minio_class):
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = False
    mock_minio_class.return_value = mock_client

    ensure_buckets()

    assert mock_client.make_bucket.call_count == 2
    mock_client.make_bucket.assert_any_call(RECEIPTS_BUCKET)
    mock_client.make_bucket.assert_any_call(PUBLIC_BUCKET)


@patch("nexus.utils.storage.Minio")
def test_ensure_buckets_skips_existing_buckets(mock_minio_class):
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    mock_minio_class.return_value = mock_client

    ensure_buckets()

    mock_client.make_bucket.assert_not_called()


@patch("nexus.utils.storage.Minio")
def test_ensure_buckets_mixed_state(mock_minio_class):
    """One bucket exists, one doesn't — only creates the missing one."""
    mock_client = MagicMock()
    mock_client.bucket_exists.side_effect = [True, False]  # receipts exists, public doesn't
    mock_minio_class.return_value = mock_client

    ensure_buckets()

    mock_client.make_bucket.assert_called_once_with(PUBLIC_BUCKET)


# ── upload_receipt ───────────────────────────────────────────────────────────


@patch("nexus.utils.storage.Minio")
def test_upload_receipt_uploads_file_and_returns_url(mock_minio_class):
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "http://minio/receipts/test.jpg?signature=abc"
    mock_minio_class.return_value = mock_client

    url = upload_receipt("/tmp/test-receipt.jpg", object_name="receipt-001.jpg")

    assert url == "http://minio/receipts/test.jpg?signature=abc"
    mock_client.fput_object.assert_called_once_with(
        RECEIPTS_BUCKET, "receipt-001.jpg", "/tmp/test-receipt.jpg"
    )
    mock_client.presigned_get_object.assert_called_once()


@patch("nexus.utils.storage.Minio")
def test_upload_receipt_uses_filename_when_no_object_name(mock_minio_class):
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "http://minio/url"
    mock_minio_class.return_value = mock_client

    url = upload_receipt("/tmp/shopping.jpg")

    assert url is not None
    mock_client.fput_object.assert_called_once_with(
        RECEIPTS_BUCKET, "shopping.jpg", "/tmp/shopping.jpg"
    )


@patch("nexus.utils.storage.Minio")
def test_upload_receipt_with_pathlib_path(mock_minio_class):
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "http://minio/url"
    mock_minio_class.return_value = mock_client

    url = upload_receipt(Path("/tmp/shopping.jpg"))

    assert url is not None
    mock_client.fput_object.assert_called_once()


@patch("nexus.utils.storage.Minio")
def test_upload_receipt_ensures_buckets_first(mock_minio_class):
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = False
    mock_client.presigned_get_object.return_value = "http://minio/url"
    mock_minio_class.return_value = mock_client

    upload_receipt("/tmp/test.jpg")
    # ensure_buckets is called -> make_bucket should have been called
    assert mock_client.make_bucket.call_count >= 1


# ── upload_receipt_bytes ─────────────────────────────────────────────────────


@patch("nexus.utils.storage.Minio")
def test_upload_receipt_bytes_uploads_and_returns_url(mock_minio_class):
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "http://minio/receipts/img.jpg?signature=xyz"
    mock_minio_class.return_value = mock_client

    url = upload_receipt_bytes(b"fake_image_data", "receipt-002.jpg")

    assert url == "http://minio/receipts/img.jpg?signature=xyz"
    mock_client.put_object.assert_called_once()
    call_args = mock_client.put_object.call_args[0]
    assert call_args[0] == RECEIPTS_BUCKET  # bucket_name
    assert call_args[1] == "receipt-002.jpg"  # object_name
    # data passed as BytesIO
    assert call_args[2].read() == b"fake_image_data"
    assert call_args[3] == len(b"fake_image_data")  # length


@patch("nexus.utils.storage.Minio")
def test_upload_receipt_bytes_sends_content_type(mock_minio_class):
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "http://minio/url"
    mock_minio_class.return_value = mock_client

    upload_receipt_bytes(b"data", "img.jpg")

    call_kwargs = mock_client.put_object.call_args[1]
    assert call_kwargs["content_type"] == "image/jpeg"


@patch("nexus.utils.storage.Minio")
def test_upload_receipt_bytes_ensures_buckets(mock_minio_class):
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = False
    mock_client.presigned_get_object.return_value = "http://minio/url"
    mock_minio_class.return_value = mock_client

    upload_receipt_bytes(b"data", "img.jpg")
    assert mock_client.make_bucket.call_count >= 1


@patch("nexus.utils.storage.Minio")
def test_upload_receipt_bytes_presigned_url_expiry(mock_minio_class):
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "http://minio/url"
    mock_minio_class.return_value = mock_client

    upload_receipt_bytes(b"data", "img.jpg")

    presigned_call = mock_client.presigned_get_object.call_args
    assert presigned_call[0][0] == RECEIPTS_BUCKET
    assert presigned_call[0][1] == "img.jpg"
    # expires=timedelta(days=7) — check that the kwarg is passed
    assert "expires" in presigned_call[1]
