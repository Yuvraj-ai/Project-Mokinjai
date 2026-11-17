"""The upload gate shared by HTTP uploads and cloud imports.

Both paths must reject the same types and the same size, or a provider import would
become a way to get a file into the library that the upload route would have refused.
"""

from app.config import get_settings
from app.utils.errors import PayloadTooLargeException

# Extraction's input contract: the types the sandbox libraries (pypdf, python-docx,
# openpyxl, pandas) can read. PPTX and HTML are deferred.
ALLOWED_UPLOAD_MIME_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)


def normalise_content_type(raw: str | None) -> str:
    """The declared type without parameters, lower-cased."""
    return (raw or "").split(";", 1)[0].strip().lower()


def enforce_size(size: int) -> None:
    """Raise `PayloadTooLargeException` above `STORAGE_MAX_UPLOAD_BYTES`."""
    limit = get_settings().STORAGE_MAX_UPLOAD_BYTES
    if size > limit:
        raise PayloadTooLargeException(f"File exceeds the {limit} byte limit")
