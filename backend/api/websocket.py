"""
PortOrange — WebSocket Manager

Manages active WebSocket connections for real-time dashboard updates.
Broadcasts state-change events and stats to all connected clients.
"""

import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import Any


class WebSocketManager:
    """
    Manages a pool of active WebSocket connections.

    Provides broadcast capabilities for pushing real-time updates
    to all connected dashboard clients.
    """

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        print(f"  📡 WebSocket client connected "
              f"({len(self._connections)} active)")

    async def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        print(f"  📡 WebSocket client disconnected "
              f"({len(self._connections)} active)")

    async def broadcast(self, message: dict[str, Any]):
        """
        Send a JSON message to all connected clients.
        Automatically removes stale connections.
        """
        if not self._connections:
            return

        payload = json.dumps(message)
        stale: list[WebSocket] = []

        async with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)

        # Clean up stale connections
        if stale:
            async with self._lock:
                for ws in stale:
                    if ws in self._connections:
                        self._connections.remove(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


# Global singleton
ws_manager = WebSocketManager()
