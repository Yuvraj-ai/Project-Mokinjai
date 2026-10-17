"""The object-storage interface (ADR-011).

Bytes live behind one interface whether they are on disk or in a bucket, so nothing
above this module knows which. The backend is chosen in `get_storage()`.
"""

from typing import Protocol


class StorageError(RuntimeError):
    """The backing store could not complete an operation."""


class ObjectNotFoundError(StorageError):
    """The key does not exist in the backing store."""


class StorageBackend(Protocol):
    """What both backends provide. Structural, not inherited.

    A Protocol rather than an ABC so a test double is simply an object with these
    methods — no import from this package, no registration, no subclass.
    """

    name: str  # "filesystem" | "s3" — recorded per document in metadata_

    async def upload_file(self, key: str, data: bytes, *, content_type: str) -> None:
        """Write `data` at `key`, replacing anything already there."""
        ...

    async def download_file(self, key: str) -> bytes:
        """Read `key`. Raises ObjectNotFoundError if it is not there."""
        ...

    async def delete_file(self, key: str) -> None:
        """Remove `key`. Removing a key that is not there is not an error."""
        ...

    async def exists(self, key: str) -> bool:
        """Whether `key` is present.

        Replaces the `list_files` that ADR-011 names: the `documents` table is the
        index of what is stored, so nothing has a caller for a bucket listing. See the
        spec's section 2.
        """
        ...


def build_storage_key(workspace_id: str, knowledge_base_id: str, document_id: str) -> str:
    """The object key for one document.

    Workspace-leading so deleting a workspace's objects is one prefix delete later;
    UUID-leaved so two uploads of the same filename cannot collide. The function takes
    no filename and no other client-supplied text, which is the whole path-traversal
    defence: a hostile name has nowhere to enter the key.
    """
    return f"workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/documents/{document_id}"
