from contextlib import asynccontextmanager
import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.logging import logger
from app.middleware.public_auth import PublicAuthError, public_error_response
from app.routers import (
    auth,
    workspaces,
    workflows,
    executions,
    files,
    prompts,
    llm_profiles,
    structured_outputs,
    skills,
    tools,
    external_databases,
    connectors,
    agents,
    playground,
    api_keys,
    search_credentials,
)
from app.routers.public import router as public_router
from app.utils.errors import AppException
from app.websocket.execution_ws import execution_websocket
from app.services.otp_store import otp_store
from app.services.sessions import prune_expired_sessions
from app.database import async_session

settings = get_settings()

# Session pruning cadence. The cleanup loop ticks once a minute; this is how many
# seconds must elapse between prunes.
_PRUNE_INTERVAL_SECONDS = 24 * 60 * 60


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup — AI Agent Builder API initializing")
    logger.info(f"CORS allowed origin: {settings.FRONTEND_URL}")

    async def cleanup_loop():
        """Housekeeping for the process: OTP expiry every minute, session pruning daily.

        Pruning runs on the first tick so a process that restarts more often than
        daily still reaps, then at most once per day. It opens its own session from
        app.database.async_session: this loop runs outside any request, so there is
        no request-scoped session to borrow.
        """
        seconds_until_prune = 0
        while True:
            await asyncio.sleep(60)
            otp_store.cleanup_expired()

            if seconds_until_prune <= 0:
                try:
                    async with async_session() as db:
                        removed = await prune_expired_sessions(db)
                except Exception:
                    # A transient database error must not kill the loop: that would
                    # silently stop the OTP cleanup above too. Retry next cycle.
                    logger.exception("Session pruning failed")
                else:
                    if removed:
                        logger.info(f"Pruned {removed} expired session(s)")
                seconds_until_prune = _PRUNE_INTERVAL_SECONDS
            seconds_until_prune -= 60

    cleanup_task = asyncio.create_task(cleanup_loop())
    yield
    cleanup_task.cancel()
    logger.info("Application shutdown")


app = FastAPI(
    title="AI Agent Builder API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} — status: {response.status_code}")
    return response

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(workflows.router, prefix="/api/workspaces/{workspace_id}/workflows", tags=["workflows"])
app.include_router(executions.router, prefix="/api/workspaces/{workspace_id}", tags=["executions"])
app.include_router(files.router, prefix="/api/workspaces/{workspace_id}/files", tags=["files"])
app.include_router(prompts.router, prefix="/api/workspaces/{workspace_id}/prompts", tags=["prompts"])
app.include_router(llm_profiles.router, prefix="/api/workspaces/{workspace_id}/llm-profiles", tags=["llm-profiles"])
app.include_router(
    structured_outputs.router,
    prefix="/api/workspaces/{workspace_id}/structured-outputs",
    tags=["structured-outputs"],
)
app.include_router(tools.router, prefix="/api/workspaces/{workspace_id}/tools", tags=["tools"])
app.include_router(
    skills.router,
    prefix="/api/workspaces/{workspace_id}/skills",
    tags=["skills"],
)
app.include_router(
    external_databases.router,
    prefix="/api/workspaces/{workspace_id}/external-databases",
    tags=["external-databases"],
)
app.include_router(
    connectors.router,
    prefix="/api/workspaces/{workspace_id}/connectors",
    tags=["connectors"],
)
app.include_router(agents.router, prefix="/api/workspaces/{workspace_id}/agents", tags=["agents"])
app.include_router(
    playground.router,
    prefix="/api/workspaces/{workspace_id}/playground",
    tags=["playground"],
)
app.include_router(
    api_keys.router,
    prefix="/api/workspaces/{workspace_id}/api-keys",
    tags=["api-keys"],
)
app.include_router(
    search_credentials.router,
    prefix="/api/workspaces/{workspace_id}/search-credentials",
    tags=["search-credentials"],
)


@app.get("/health")
async def health_check():
    logger.debug("Health check requested")
    return {"status": "ok"}


# The public /v1 surface: its own sub-application so its OpenAPI document
# cannot advertise internal routes, with the public error envelope in place
# of FastAPI's default {detail} shape. Bearer-key auth only — no cookies, so
# permissive CORS with credentials off is correct for a server-to-server API.
public_app = FastAPI(
    title="Mokinjay Public API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@public_app.exception_handler(PublicAuthError)
async def public_auth_error_handler(request: Request, exc: PublicAuthError):
    status_by_code = {
        "invalid_api_key": 401,
        "key_disabled": 401,
        "key_expired": 401,
        "conversation_not_found": 404,
        "agent_unavailable": 403,
        "agent_mismatch": 409,
        "rate_limit_exceeded": 429,
        "credit_limit_exceeded": 402,
        "invalid_request": 400,
    }
    status = status_by_code.get(exc.code, 400)
    headers = {}
    if exc.code == "rate_limit_exceeded":
        # Seconds until the next fixed window starts.
        headers["Retry-After"] = str(60 - (datetime.now(timezone.utc).second))
    return JSONResponse(
        status_code=status,
        headers=headers,
        content=public_error_response(exc.code, exc.message, status, f"req_{uuid.uuid4().hex[:16]}")["body"],
    )


@public_app.middleware("http")
async def attach_rate_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in getattr(request.state, "rate_headers", {}).items():
        response.headers[name] = value
    return response


@public_app.exception_handler(AppException)
async def public_not_found_handler(request: Request, exc: AppException):
    status = exc.status_code if hasattr(exc, "status_code") else 404
    code = "not_found" if status == 404 else "invalid_request"
    return JSONResponse(
        status_code=status,
        content=public_error_response(code, str(exc.detail), status, f"req_{uuid.uuid4().hex[:16]}")["body"],
    )


@public_app.exception_handler(RequestValidationError)
async def public_validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=public_error_response(
            "invalid_request", "The request body is malformed.", 400, f"req_{uuid.uuid4().hex[:16]}"
        )["body"],
    )


public_app.include_router(public_router)
app.mount("/v1", public_app)


@app.get("/v1/models", include_in_schema=False)
async def list_models_stub():
    return {"object": "list", "data": []}


@app.websocket("/ws/executions/{execution_id}")
async def ws_execution(websocket: WebSocket, execution_id: str):
    logger.info(f"WebSocket connection opened for execution {execution_id}")
    await execution_websocket(websocket, execution_id)
