"""Staging the run's files and the execute_python adapter."""

import json
from pathlib import Path

import pytest

from app.models.knowledge import DOCUMENT_STATUS_STORED, Document
from app.services.agent_runtime import _attachment_name, _stage_files
from app.services.agent_tools import STDOUT_LIMIT, TRUNCATION_MARKER, sandbox_python_tool
from app.services.sandbox.backends import SandboxConfig
from app.services.sandbox.errors import ErrorInfo, ErrorKind
from app.services.sandbox.session import ExecResult, GeneratedFile, SandboxSession
from app.services.storage import ObjectNotFoundError


def document(name: str, url: str = "workspaces/ws/files/doc") -> Document:
    return Document(
        id=f"id-{name}",
        workspace_id="ws",
        filename=name,
        file_url=url,
        file_size=1,
        mime_type="text/plain",
        status=DOCUMENT_STATUS_STORED,
    )


class FakeStorage:
    def __init__(self, contents: dict[str, bytes], missing: set[str] | None = None):
        self._contents = contents
        self._missing = missing or set()

    async def download_file(self, key: str) -> bytes:
        if key in self._missing:
            raise ObjectNotFoundError(key)
        return self._contents[key]


class FakeSession:
    def __init__(self, result: ExecResult):
        self.result = result
        self.code: str | None = None

    def execute_python(self, code: str) -> ExecResult:
        self.code = code
        return self.result


def test_names_lose_paths_characters_and_leading_dots():
    used: set[str] = set()

    assert _attachment_name("../a b?.pdf", "fallback", used) == "a b.pdf"
    assert _attachment_name("...hidden.txt", "fallback", used) == "hidden.txt"
    assert _attachment_name("/etc/passwd", "fallback", used) == "passwd"


def test_a_duplicate_name_is_numbered_and_the_cap_holds():
    used: set[str] = set()
    first = _attachment_name("report.xlsx", "fallback", used)
    used.add(first)
    second = _attachment_name("report.xlsx", "fallback", used)

    assert (first, second) == ("report.xlsx", "report (2).xlsx")

    used = {_attachment_name("x" * 300 + ".pdf", "fallback", set())}
    long_name = _attachment_name("x" * 300 + ".pdf", "fallback", used)
    assert len(long_name) <= 120


def test_an_empty_name_falls_back():
    assert _attachment_name(None, "doc-id", set()) == "doc-id"
    assert _attachment_name("   ", "doc-id", set()) == "doc-id"


@pytest.mark.asyncio
async def test_staging_writes_bytes_and_skips_a_missing_object(monkeypatch, tmp_path):
    documents = [document("notes.txt", "a"), document("gone.txt", "b")]
    monkeypatch.setattr(
        "app.services.agent_runtime.get_storage",
        lambda: FakeStorage({"a": b"hello"}, missing={"b"}),
    )

    staging, names = await _stage_files(documents)

    assert staging is not None
    assert names == ["notes.txt"]
    assert (staging / "notes.txt").read_bytes() == b"hello"
    assert list(staging.iterdir()) == [staging / "notes.txt"]


@pytest.mark.asyncio
async def test_no_documents_means_no_directory():
    staging, names = await _stage_files([])

    assert staging is None
    assert names == []


@pytest.mark.asyncio
async def test_execute_python_returns_stdout_stderr_and_files():
    session = FakeSession(
        ExecResult(
            stdout="mean 4.2\n",
            stderr="",
            error=None,
            generated_files=[GeneratedFile(name="chart.png", size=3, data=b"png")],
        )
    )
    tool = sandbox_python_tool(session, ["sales.csv"])

    payload = json.loads(await tool.ainvoke({"code": "print(1)"}))

    assert session.code == "print(1)"
    assert payload == {
        "stdout": "mean 4.2\n",
        "stderr": "",
        "ok": True,
        "error": None,
        "files": ["chart.png"],
    }
    assert "sales.csv" in tool.description
    assert "/app/data" in tool.description


@pytest.mark.asyncio
async def test_a_sandbox_error_is_reported_not_raised():
    session = FakeSession(
        ExecResult(
            stdout="",
            stderr="Traceback…",
            error=ErrorInfo(kind=ErrorKind.TIMEOUT.value, message="took too long"),
        )
    )
    payload = json.loads(
        await sandbox_python_tool(session, []).ainvoke({"code": "while True: pass"})
    )

    assert payload["ok"] is False
    assert payload["error"] == "took too long"


@pytest.mark.asyncio
async def test_stdout_is_truncated_with_a_visible_marker():
    session = FakeSession(
        ExecResult(stdout="x" * (STDOUT_LIMIT + 50), stderr="", error=None)
    )

    payload = json.loads(await sandbox_python_tool(session, []).ainvoke({"code": "print(1)"}))

    assert len(payload["stdout"]) == STDOUT_LIMIT + len(TRUNCATION_MARKER)
    assert payload["stdout"].endswith(TRUNCATION_MARKER)


def test_the_tool_is_not_offered_on_the_subprocess_backend():
    session = SandboxSession(config=SandboxConfig(backend="subprocess"))

    assert session.uses_docker is False
    assert SandboxSession(config=SandboxConfig(backend="docker")).uses_docker is True
