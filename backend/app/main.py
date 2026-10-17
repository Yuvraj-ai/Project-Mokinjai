from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.logging import logger
from app.routers import (
    auth,
    workspaces,
    workflows,
    executions,
    knowledge,
    prompts,
    llm_profiles,
    structured_outputs,
    skills,
    tools,
    external_databases,
    connectors,
)
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
app.include_router(knowledge.router, prefix="/api/workspaces/{workspace_id}/knowledge-bases", tags=["knowledge"])
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


@app.get("/health")
async def health_check():
    logger.debug("Health check requested")
    return {"status": "ok"}


@app.get("/v1/models", include_in_schema=False)
async def list_models_stub():
    return {"object": "list", "data": []}


@app.websocket("/ws/executions/{execution_id}")
async def ws_execution(websocket: WebSocket, execution_id: str):
    logger.info(f"WebSocket connection opened for execution {execution_id}")
    await execution_websocket(websocket, execution_id)
