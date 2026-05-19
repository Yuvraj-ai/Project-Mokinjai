import json
from fastapi import WebSocket, WebSocketDisconnect
from app.utils.security import decode_token

class ConnectionManager:
    """Manages WebSocket connections for execution updates."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, execution_id: str):
        await websocket.accept()
        if execution_id not in self.active_connections:
            self.active_connections[execution_id] = []
        self.active_connections[execution_id].append(websocket)

    def disconnect(self, websocket: WebSocket, execution_id: str):
        if execution_id in self.active_connections:
            try:
                self.active_connections[execution_id].remove(websocket)
            except ValueError:
                pass
            if not self.active_connections[execution_id]:
                del self.active_connections[execution_id]

    async def send_event(self, execution_id: str, event: dict):
        if execution_id not in self.active_connections:
            return
        message = json.dumps(event)
        dead_connections = []
        for connection in self.active_connections[execution_id]:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)
        for conn in dead_connections:
            self.disconnect(conn, execution_id)

manager = ConnectionManager()

async def execution_websocket(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for real-time execution updates."""
    from app.config import get_settings
    settings = get_settings()
    origin = websocket.headers.get("origin", "")
    if origin and origin not in settings.CORS_ORIGINS:
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing auth token")
        return

    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = payload.get("sub")

    from app.database import async_session
    from sqlalchemy import select
    from app.models.execution import Execution
    from app.models.workspace import WorkspaceMember

    async with async_session() as db:
        result = await db.execute(select(Execution).where(Execution.id == execution_id))
        execution = result.scalar_one_or_none()
        if execution is None:
            await websocket.close(code=4004, reason="Execution not found")
            return

        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == execution.workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        if result.scalar_one_or_none() is None:
            await websocket.close(code=4003, reason="Access denied")
            return

    await manager.connect(websocket, execution_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except (json.JSONDecodeError, TypeError):
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
    finally:
        manager.disconnect(websocket, execution_id)
