"""WebSocket connection manager.

Broadcasts live analysis progress, new events and status changes to every
connected client. The frontend filters by `video_id`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info("WS client connected (%d active)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info("WS client disconnected (%d active)", len(self._connections))

    async def broadcast(self, message_type: str, video_id: int, payload: Any) -> None:
        message = json.dumps(
            {"type": message_type, "video_id": video_id, "payload": payload},
            default=str,
        )
        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)


manager = ConnectionManager()
