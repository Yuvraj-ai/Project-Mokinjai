import json
from fastapi import WebSocket, WebSocketDisconnect
from app.database import async_session
from app.logging import logger
from app.middleware.auth import resolve_session_and_user
from app.services.sessions import session_is_live
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
            session, _ = await resolve_session_and_user(token, db)
        except UnauthorizedException:
            logger.warning(f"WebSocket auth failed for execution {execution_id}")
            await websocket.close(code=4001)
            return
        session_id = session.id

    await manager.connect(websocket, execution_id)
    try:
        while True:
            await websocket.receive_text()

            # Re-validate on every inbound message: a socket accepted while the
            # session was live must not keep receiving events after a logout revokes
            # it. The loop only wakes when the client sends, so this is the earliest
            # point the revocation can be noticed on an idle connection.
            async with async_session() as db:
                live = await session_is_live(session_id, db)
            if not live:
                logger.warning(
                    f"WebSocket closing — session {session_id} was revoked or expired"
                )
                manager.disconnect(websocket, execution_id)
                await websocket.close(code=4001)
                return
    except WebSocketDisconnect:
        manager.disconnect(websocket, execution_id)
