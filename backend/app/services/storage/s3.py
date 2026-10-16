"""An S3-compatible bucket: AWS S3 or MinIO (ADR-011)."""

import asyncio

import boto3
from botocore.exceptions import ClientError

from app.services.storage.base import ObjectNotFoundError, StorageError


class S3Storage:
    """The abstraction's object-storage side, with nothing S3-shaped leaking upward.

    boto3 is synchronous, so every call goes through `asyncio.to_thread`: without it a
    25 MiB upload would block every other request in the process for the transfer.
    """

    name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str = "",
        region: str = "",
        access_key_id: str,
        secret_access_key: str,
    ):
        self.bucket = bucket
        # Constructing a client makes no network call — the first request is the first
        # operation. That is what lets `get_storage()` be tested with fake credentials
        # and no S3-compatible service present.
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region or None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    async def upload_file(self, key: str, data: bytes, *, content_type: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except ClientError as exc:
            raise StorageError(f"S3 upload failed for {key!r}: {exc}") from exc

    async def download_file(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self.bucket, Key=key
            )
        except ClientError as exc:
            if _is_missing(exc):
                raise ObjectNotFoundError(key) from exc
            raise StorageError(f"S3 download failed for {key!r}: {exc}") from exc
        return await asyncio.to_thread(response["Body"].read)

    async def delete_file(self, key: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.delete_object, Bucket=self.bucket, Key=key
            )
        except ClientError as exc:
            raise StorageError(f"S3 delete failed for {key!r}: {exc}") from exc

    async def exists(self, key: str) -> bool:
        try:
            await asyncio.to_thread(
                self._client.head_object, Bucket=self.bucket, Key=key
            )
        except ClientError as exc:
            if _is_missing(exc):
                return False
            raise StorageError(f"S3 head failed for {key!r}: {exc}") from exc
        return True


def _is_missing(exc: ClientError) -> bool:
    """S3 has no not-found exception; a missing object is a 404 ClientError."""
    return exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404
