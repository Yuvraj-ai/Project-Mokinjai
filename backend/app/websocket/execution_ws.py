import json
from fastapi import WebSocket, WebSocketDisconnect
from app.database import async_session
from app.logging import logger
from app.middleware.auth import resolve_session_and_user
from app.utils.errors import UnauthorizedException


class ConnectionManager:
    """Manages WebSocket connections for execution updates."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, execution_id: str):
        await websocket.accept()
        if execution_id not in self.active_connections:
            self.active_connections[execution_id] = []
        self.active_connections[execution_id].append(websocket)
        logger.info(f"WebSocket connected for execution {execution_id} (total: {len(self.active_connections[execution_id])})")

    def disconnect(self, websocket: WebSocket, execution_id: str):
        if execution_id in self.active_connections:
            self.active_connections[execution_id].remove(websocket)
            if not self.active_connections[execution_id]:
                del self.active_connections[execution_id]
            logger.info(f"WebSocket disconnected for execution {execution_id}")

    async def send_event(self, execution_id: str, event: dict):
        if execution_id in self.active_connections:
            message = json.dumps(event)
            for connection in self.active_connections[execution_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    pass


manager = ConnectionManager()


async def execution_websocket(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for real-time execution updates.

    Requires a valid access token with a live session. Previously a missing token
    skipped verification entirely, and any decodable JWT — including a refresh
    token — was accepted, so this path bypassed session revocation completely.
    """
    token = websocket.query_params.get("token")
    if not token:
        logger.warning(f"WebSocket rejected — no token for execution {execution_id}")
        await websocket.close(code=4001)
        return

    async with async_session() as db:
        try:
            await resolve_session_and_user(token, db)
        except UnauthorizedException:
            logger.warning(f"WebSocket auth failed for execution {execution_id}")
            await websocket.close(code=4001)
            return

    await manager.connect(websocket, execution_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, execution_id)
