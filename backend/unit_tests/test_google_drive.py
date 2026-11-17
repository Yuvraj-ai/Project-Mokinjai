"""Drive downloads and exports, with the upload ceiling enforced while streaming."""

from types import SimpleNamespace

import httpx
import pytest

from app.services import google_drive
from app.utils.errors import BadRequestException, PayloadTooLargeException

DOC = "application/vnd.google-apps.document"
SHEET = "application/vnd.google-apps.spreadsheet"
SLIDES = "application/vnd.google-apps.presentation"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def transport_for(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_a_google_doc_is_exported_as_docx():
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, content=b"docx-bytes")

    data = await google_drive.download("file-1", DOC, "token", transport=transport_for(handler))

    assert data == b"docx-bytes"
    assert str(seen[0]).find("/files/file-1/export") != -1
    assert seen[0].params["mimeType"] == DOCX


@pytest.mark.asyncio
async def test_a_spreadsheet_is_exported_as_xlsx():
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, content=b"xlsx")

    await google_drive.download("file-1", SHEET, "token", transport=transport_for(handler))

    assert seen[0].params["mimeType"] == XLSX


@pytest.mark.asyncio
async def test_a_presentation_is_exported_as_pdf():
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, content=b"pdf")

    await google_drive.download("file-1", SLIDES, "token", transport=transport_for(handler))

    assert seen[0].params["mimeType"] == "application/pdf"


@pytest.mark.asyncio
async def test_a_binary_file_is_downloaded_with_alt_media():
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, content=b"%PDF")

    await google_drive.download(
        "file-1", "application/pdf", "token", transport=transport_for(handler)
    )

    assert seen[0].params["alt"] == "media"
    assert "/export" not in str(seen[0])


@pytest.mark.asyncio
async def test_an_unsupported_google_type_is_rejected_before_any_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200)

    with pytest.raises(BadRequestException):
        await google_drive.download(
            "file-1",
            "application/vnd.google-apps.drawing",
            "token",
            transport=transport_for(handler),
        )

    assert calls == []


@pytest.mark.asyncio
async def test_a_download_over_the_ceiling_is_aborted_mid_stream(monkeypatch):
    monkeypatch.setattr(
        google_drive,
        "get_settings",
        lambda: SimpleNamespace(STORAGE_MAX_UPLOAD_BYTES=10),
    )

    def handler(_request):
        return httpx.Response(200, content=b"x" * 11)

    with pytest.raises(PayloadTooLargeException):
        await google_drive.download(
            "file-1", "application/pdf", "token", transport=transport_for(handler)
        )


@pytest.mark.asyncio
async def test_a_401_is_reported_as_an_expired_pick():
    def handler(_request):
        return httpx.Response(401, json={"error": {"message": "Invalid Credentials"}})

    with pytest.raises(google_drive.GoogleDriveAuthError) as caught:
        await google_drive.download(
            "file-1", "application/pdf", "token", transport=transport_for(handler)
        )

    assert "pick the files again" in str(caught.value)


@pytest.mark.asyncio
async def test_a_403_is_reported_as_permission_or_quota():
    def permission(_request):
        return httpx.Response(
            403,
            json={"error": {"errors": [{"reason": "insufficientFilePermissions"}]}},
        )

    def quota(_request):
        return httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})

    with pytest.raises(google_drive.GoogleDriveAuthError) as denied:
        await google_drive.download(
            "file-1", "application/pdf", "token", transport=transport_for(permission)
        )
    with pytest.raises(google_drive.GoogleDriveAuthError) as limited:
        await google_drive.download(
            "file-1", "application/pdf", "token", transport=transport_for(quota)
        )

    assert "permission" in str(denied.value)
    assert "quota" in str(limited.value)


@pytest.mark.asyncio
async def test_metadata_is_fetched_by_id():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={"id": "file-1", "name": "Plan", "mimeType": DOC, "size": "123"},
        )

    metadata = await google_drive.get_file_metadata(
        "file-1", "token", transport=transport_for(handler)
    )

    assert seen[0].url.path == "/drive/v3/files/file-1"
    assert seen[0].url.params["fields"] == "id,name,mimeType,size"
    assert metadata == {
        "id": "file-1",
        "name": "Plan",
        "mime_type": DOC,
        "size": 123,
    }
