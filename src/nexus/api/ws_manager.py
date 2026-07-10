"""WebSocket connection manager for real-time task updates."""

import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections keyed by user_id."""

    def __init__(self):
        self._connections: dict[int, list[WebSocket]] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        self._connections.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not self._connections.get(user_id):
            self._connections.pop(user_id, None)

    async def broadcast(self, user_id: int, event: str, data: dict[str, Any]):
        """Send an event to all WebSocket connections for a user."""
        payload = json.dumps({"event": event, "data": data})
        for ws in self._connections.get(user_id, []):
            try:
                await ws.send_text(payload)
            except Exception:
                self.disconnect(user_id, ws)


manager = ConnectionManager()
