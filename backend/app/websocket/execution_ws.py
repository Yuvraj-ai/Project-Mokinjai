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
            self.active_connections[execution_id].remove(websocket)
            if not self.active_connections[execution_id]:
                del self.active_connections[execution_id]

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
    """WebSocket endpoint for real-time execution updates."""
    # Authenticate via query param
    token = websocket.query_params.get("token")
    if token:
        payload = decode_token(token)
        if payload is None:
            await websocket.close(code=4001)
            return

    await manager.connect(websocket, execution_id)
    try:
        while True:
            # Keep connection alive, wait for client messages
            data = await websocket.receive_text()
            # Client can send ping/pong or commands
    except WebSocketDisconnect:
        manager.disconnect(websocket, execution_id)
