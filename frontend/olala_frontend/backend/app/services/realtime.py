import asyncio
import secrets
from dataclasses import dataclass

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


@dataclass
class WSConnection:
    connection_id: str
    issue_id: str
    websocket: WebSocket
    user_id: str | None = None
    nickname: str | None = None


class RealtimeManager:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, WSConnection]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, issue_id: str, websocket: WebSocket) -> WSConnection:
        await websocket.accept()
        connection = WSConnection(
            connection_id=secrets.token_hex(8),
            issue_id=issue_id,
            websocket=websocket,
        )

        async with self._lock:
            room = self._rooms.setdefault(issue_id, {})
            room[connection.connection_id] = connection

        return connection

    async def update_identity(
        self,
        connection: WSConnection,
        user_id: str | None,
        nickname: str | None,
    ) -> None:
        async with self._lock:
            room = self._rooms.get(connection.issue_id)
            if room is None:
                return
            target = room.get(connection.connection_id)
            if target is None:
                return
            target.user_id = user_id
            target.nickname = nickname

    async def disconnect(self, connection: WSConnection) -> None:
        async with self._lock:
            room = self._rooms.get(connection.issue_id)
            if room is not None:
                room.pop(connection.connection_id, None)
                if not room:
                    self._rooms.pop(connection.issue_id, None)

    async def room_size(self, issue_id: str) -> int:
        async with self._lock:
            return len(self._rooms.get(issue_id, {}))

    async def room_connections(self, issue_id: str) -> list[WSConnection]:
        async with self._lock:
            room = self._rooms.get(issue_id, {})
            return list(room.values())

    async def send_json(self, connection: WSConnection, payload: dict[str, object]) -> bool:
        try:
            await connection.websocket.send_json(payload)
            return True
        except (RuntimeError, WebSocketDisconnect):
            await self.disconnect(connection)
            return False

    async def broadcast(self, issue_id: str, payload: dict[str, object]) -> None:
        for connection in await self.room_connections(issue_id):
            await self.send_json(connection, payload)
