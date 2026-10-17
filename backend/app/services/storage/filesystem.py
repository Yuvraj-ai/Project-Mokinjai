"""Bytes on the local disk. ADR-011's fallback, and the default in development."""

from pathlib import Path

from app.services.storage.base import ObjectNotFoundError, StorageError


class FilesystemStorage:
    """One root directory, with every key resolved inside it.

    `content_type` is accepted and ignored: it is stored on the `Document` row and
    replayed by the download endpoint, so the filesystem has nowhere to put it and does
    not pretend otherwise.
    """

    name = "filesystem"

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        # Keys come from build_storage_key, which takes no client input, so this cannot
        # fire today. It is here because for a filesystem backend a bad key is an
        # arbitrary file write.
        if candidate != self.root and self.root not in candidate.parents:
            raise StorageError(f"Storage key escapes the storage root: {key!r}")
        return candidate

    async def upload_file(self, key: str, data: bytes, *, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def download_file(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFoundError(key)
        return path.read_bytes()

    async def delete_file(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()
