"""The storage abstraction (ADR-011).

`get_storage()` is the only reader of the storage settings. Object storage when a bucket
and a key pair are configured; the local filesystem otherwise. The interface is a
structural Protocol, so a test double needs no import from this package.
"""

from app.config import get_settings
from app.services.storage.base import (
    ObjectNotFoundError,
    StorageBackend,
    StorageError,
    build_storage_key,
)
from app.services.storage.filesystem import FilesystemStorage
from app.services.storage.s3 import S3Storage

__all__ = [
    "FilesystemStorage",
    "ObjectNotFoundError",
    "S3Storage",
    "StorageBackend",
    "StorageError",
    "build_storage_key",
    "get_storage",
]


def get_storage() -> StorageBackend:
    """The configured backend.

    Credential completeness rather than an explicit switch, so an empty `.env` can only
    ever select the backend that works with an empty `.env` (ADR-011).
    """
    settings = get_settings()
    if (
        settings.STORAGE_S3_BUCKET
        and settings.STORAGE_S3_ACCESS_KEY_ID
        and settings.STORAGE_S3_SECRET_ACCESS_KEY
    ):
        return S3Storage(
            bucket=settings.STORAGE_S3_BUCKET,
            endpoint_url=settings.STORAGE_S3_ENDPOINT_URL,
            region=settings.STORAGE_S3_REGION,
            access_key_id=settings.STORAGE_S3_ACCESS_KEY_ID,
            secret_access_key=settings.STORAGE_S3_SECRET_ACCESS_KEY,
        )
    return FilesystemStorage(settings.STORAGE_LOCAL_PATH)
