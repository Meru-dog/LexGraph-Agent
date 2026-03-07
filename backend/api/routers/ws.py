"""WebSocket endpoint — pushes agent status events to the frontend.

Clients connect to /ws/{session_id} and receive JSON messages:
    {"type": "status_update", "task_id": "...", "status": "awaiting_review", ...}
"""

import asyncio
import json
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

# session_id → WebSocket connection
_connections: Dict[str, WebSocket] = {}


class ConnectionManager:
    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        _connections[session_id] = ws

    def disconnect(self, session_id: str) -> None:
        _connections.pop(session_id, None)

    async def send(self, session_id: str, payload: dict) -> None:
        ws = _connections.get(session_id)
        if ws:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                self.disconnect(session_id)

    async def broadcast(self, payload: dict) -> None:
        dead = []
        for sid, ws in list(_connections.items()):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(sid)
        for sid in dead:
            self.disconnect(sid)


ws_manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws_manager.connect(session_id, ws)
    try:
        while True:
            # Keep connection alive; client sends pings as plain text
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
