from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.logging import logger
from app.routers import auth, workspaces, workflows, executions, knowledge, prompts
from app.websocket.execution_ws import execution_websocket
from app.services.otp_store import otp_store

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup — AI Agent Builder API initializing")
    logger.info(f"CORS allowed origin: {settings.FRONTEND_URL}")

    async def cleanup_loop():
        while True:
            await asyncio.sleep(60)
            otp_store.cleanup_expired()

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


@app.get("/health")
async def health_check():
    logger.debug("Health check requested")
    return {"status": "ok"}


@app.websocket("/ws/executions/{execution_id}")
async def ws_execution(websocket: WebSocket, execution_id: str):
    logger.info(f"WebSocket connection opened for execution {execution_id}")
    await execution_websocket(websocket, execution_id)
