"""The sandbox daemon: a small FastAPI app that owns Docker on the remote host.

It imports the Docker backend and the error taxonomy, and nothing above them. It has
no idea what a tool call is; it creates a session, runs requested jobs in it, and
serves the files the jobs wrote.
"""

import io
import json
import tarfile
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.logging import logger
from app.services.sandbox.backends import docker_reachable
from app.services.sandbox.daemon.auth import verify
from app.services.sandbox.daemon.store import (
    AdmissionFull,
    InvalidSession,
    JobInProgress,
    SessionStore,
    UnknownSession,
    _extract_tar,
)
from app.services.sandbox.errors import SandboxError
from app.services.sandbox.protocol import JobRequest

UNAUTHENTICATED_PATHS = frozenset({"/health"})
# Multipart and tar overhead above the 95 MiB file cap. Bounded before the signature
# check because the port is public: an unauthenticated POST must not be able to make
# the daemon buffer an arbitrary body.
MAX_REQUEST_OVERHEAD_BYTES = 1024 * 1024


async def _reject(send, status: int, detail: str) -> None:
    payload = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": payload})


class SignatureMiddleware:
    """Verify the raw request body before FastAPI parses it.

    A dependency cannot do this: FastAPI parses multipart form fields before the
    dependency's `request.body()` runs, which leaves the stream consumed. Buffering
    here and replaying the bytes is what keeps the signed body and the parsed form the
    same bytes.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["path"] in UNAUTHENTICATED_PATHS:
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        limit = settings.STORAGE_MAX_UPLOAD_BYTES + MAX_REQUEST_OVERHEAD_BYTES
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope["headers"]
        }
        declared_length = headers.get("content-length")
        if declared_length and declared_length.isdigit() and int(declared_length) > limit:
            await _reject(send, 413, "request body exceeds the upload limit")
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > limit:
                await _reject(send, 413, "request body exceeds the upload limit")
                return
            chunks.append(chunk)
            if not message.get("more_body"):
                break
        body = b"".join(chunks)

        secret = settings.SANDBOX_DAEMON_SECRET
        reason = (
            "daemon secret is not configured"
            if not secret
            else verify(secret, headers.get("x-mokinjay-signature"), body)
        )
        if reason:
            logger.warning(f"Rejected daemon request: {reason}")
            await _reject(send, 401, reason)
            return

        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.prune_stale(get_settings().SANDBOX_MAX_RUN_SECONDS)
    yield


app = FastAPI(
    title="mokinjay-sandbox-daemon",
    lifespan=lifespan,
    # The daemon exposes exactly its own routes; FastAPI's docs would add three more
    # unauthenticated paths behind the public port.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(SignatureMiddleware)
store = SessionStore()


@app.get("/health")
async def health() -> dict:
    """Unauthenticated on purpose: the liveness probe must answer before setup."""
    return {
        "status": "ok",
        "docker": docker_reachable(get_settings().SANDBOX_DOCKER_BIN),
        "sessions": store.count(),
    }


router = APIRouter()


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def _spool_limit() -> int:
    """One staged tar, plus multipart headroom over the file ceiling."""
    return get_settings().STORAGE_MAX_UPLOAD_BYTES + MAX_REQUEST_OVERHEAD_BYTES


@router.post("/sessions/{session_id}/files", status_code=204)
async def upload_part(session_id: str, request: Request, offset: int = 0) -> Response:
    """Write one chunk of the staged tar. A retried offset overwrites, so it is safe."""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    if offset < 0:
        raise _bad_request("offset must be non-negative")
    body = await request.body()
    if offset + len(body) > _spool_limit():
        raise HTTPException(status_code=413, detail="staged tar exceeds the upload limit")

    spool = session.root / "upload.tar"
    with session.lock:
        current = spool.stat().st_size if spool.exists() else 0
        if offset > current:
            raise _bad_request("offset skips bytes that were never uploaded")
        with open(spool, "r+b" if spool.exists() else "w+b") as handle:
            handle.seek(offset)
            handle.write(body)
    return Response(status_code=204)


def _extract_spool(session, limit: int) -> None:
    spool = session.root / "upload.tar"
    with tarfile.open(spool, mode="r:*") as archive:
        _extract_tar(archive, session.root / "data", limit)
    spool.unlink(missing_ok=True)


@router.post("/sessions/{session_id}/files/finalize", status_code=204)
async def finalize_files(session_id: str) -> Response:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    spool = session.root / "upload.tar"
    if not spool.is_file():
        raise _bad_request("no staged upload to finalize")
    try:
        with session.lock:
            await run_in_threadpool(
                _extract_spool, session, get_settings().STORAGE_MAX_UPLOAD_BYTES
            )
    except (tarfile.TarError, InvalidSession) as exc:
        raise _bad_request(f"invalid staged tar: {exc}")
    return Response(status_code=204)


@router.post("/sessions")
async def create_session(
    session_id: str = Form(...),
    spec: str = Form(...),
    data: UploadFile = File(...),
) -> Response:
    try:
        fields = json.loads(spec)
    except json.JSONDecodeError:
        raise _bad_request("spec must be JSON")
    if not isinstance(fields, dict):
        raise _bad_request("spec must be a JSON object")

    payload = await data.read()
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:*")
    except tarfile.TarError:
        raise _bad_request("data must be a tar archive")

    try:
        with archive:
            session, created = await run_in_threadpool(store.create, session_id, fields, archive)
    except InvalidSession as exc:
        raise _bad_request(str(exc))
    except AdmissionFull:
        raise HTTPException(status_code=503, detail="the sandbox host is at capacity")
    except SandboxError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "kind": exc.info.kind,
                "message": exc.info.message,
                "detail": exc.info.detail,
            },
        )
    return JSONResponse(
        status_code=201 if created else 200,
        content={"session_id": session.session_id},
    )


class JobIn(BaseModel):
    job_id: str = Field(min_length=1, max_length=64)
    request: dict


@router.post("/sessions/{session_id}/jobs")
async def run_job(session_id: str, payload: JobIn) -> Response:
    try:
        request = JobRequest(**payload.request)
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=f"malformed job request: {exc}")

    # Host patience must exceed the job's own deadline; the kernel's grace is the gap.
    timeout = request.timeout + get_settings().SANDBOX_KERNEL_GRACE_SECONDS
    try:
        result = await run_in_threadpool(
            store.run_job, session_id, payload.job_id, request, timeout
        )
    except UnknownSession:
        raise HTTPException(status_code=404, detail="unknown session")
    except JobInProgress:
        raise HTTPException(status_code=409, detail="job in progress; retry later")
    except SandboxError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "kind": exc.info.kind,
                "message": exc.info.message,
                "detail": exc.info.detail,
            },
        )
    return JSONResponse(content=result)


@router.get("/sessions/{session_id}")
async def inspect_session(session_id: str) -> dict:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return {"session_id": session.session_id, "alive": session.backend.is_alive()}


@router.get("/sessions/{session_id}/outputs")
async def collect_outputs(session_id: str) -> Response:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    files = await run_in_threadpool(session.backend.collect_outputs)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, content in files:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return Response(content=buffer.getvalue(), media_type="application/x-tar")


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str) -> Response:
    try:
        await run_in_threadpool(store.delete, session_id)
    except InvalidSession as exc:
        raise _bad_request(str(exc))
    return Response(status_code=204)


app.include_router(router)
