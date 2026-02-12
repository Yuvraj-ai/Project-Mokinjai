from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, workspaces, workflows, executions, knowledge
from app.websocket.execution_ws import execution_websocket

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


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

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(workflows.router, prefix="/api/workspaces/{workspace_id}/workflows", tags=["workflows"])
app.include_router(executions.router, prefix="/api/workspaces/{workspace_id}", tags=["executions"])
app.include_router(knowledge.router, prefix="/api/workspaces/{workspace_id}/knowledge-bases", tags=["knowledge"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.websocket("/ws/executions/{execution_id}")
async def ws_execution(websocket: WebSocket, execution_id: str):
    await execution_websocket(websocket, execution_id)
