from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings, Settings
from app.database import init_db
from app.utils.mongo import MongoManager

def include_routers(app: FastAPI) -> None:
    from app.routers import auth, workspaces, workflows, executions, knowledge, users
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
    app.include_router(workflows.router, prefix="/api/workspaces/{workspace_id}/workflows", tags=["workflows"])
    app.include_router(executions.router, prefix="/api/workspaces/{workspace_id}", tags=["executions"])
    app.include_router(knowledge.router, prefix="/api/workspaces/{workspace_id}/knowledge-bases", tags=["knowledge"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    from app.database import engine
    if engine:
        await engine.dispose()
    MongoManager.close()

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    init_db(settings)

    app = FastAPI(
        title="Mokinjai API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    include_routers(app)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
        
    @app.get("/ready")
    async def readiness_check():
        from app.database import async_session
        from sqlalchemy import text
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        await MongoManager.ping()
        return {"status": "ready"}

    @app.websocket("/ws/executions/{execution_id}")
    async def ws_execution(websocket: WebSocket, execution_id: str):
        from app.websocket.execution_ws import execution_websocket
        await execution_websocket(websocket, execution_id)

    return app

app = create_app()
