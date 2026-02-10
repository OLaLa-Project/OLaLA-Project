import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
        # Banned users: {issue_id: {user_id: expiry_time}}
        self._banned_users: dict[str, dict[str, datetime]] = {}

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

    async def kick_user(
        self,
        issue_id: str,
        user_id: str,
        ban_duration_minutes: int = 10,
    ) -> int:
        """
        Kick a user from the chat room and ban them temporarily.

        Returns:
            Number of connections closed
        """
        # Add to banned list
        async with self._lock:
            banned_room = self._banned_users.setdefault(issue_id, {})
            expiry = datetime.now(timezone.utc) + timedelta(minutes=ban_duration_minutes)
            banned_room[user_id] = expiry

        # Find and close all connections for this user
        connections_to_kick = []
        async with self._lock:
            room = self._rooms.get(issue_id, {})
            for conn in room.values():
                if conn.user_id == user_id:
                    connections_to_kick.append(conn)

        # Close connections
        kicked_count = 0
        for conn in connections_to_kick:
            try:
                await conn.websocket.send_json({
                    "type": "user.kicked",
                    "issueId": issue_id,
                    "reason": f"관리자에 의해 퇴장되었습니다. ({ban_duration_minutes}분 후 재입장 가능)",
                    "banDuration": ban_duration_minutes,
                })
                await conn.websocket.close(code=4003, reason="kicked")
                kicked_count += 1
            except Exception:
                pass
            finally:
                await self.disconnect(conn)

        return kicked_count

    async def is_banned(self, issue_id: str, user_id: str) -> bool:
        """Check if a user is currently banned from the issue chat room."""
        async with self._lock:
            banned_room = self._banned_users.get(issue_id, {})
            expiry = banned_room.get(user_id)

            if expiry is None:
                return False

            # Check if ban has expired
            if datetime.now(timezone.utc) >= expiry:
                # Remove expired ban
                banned_room.pop(user_id, None)
                if not banned_room:
                    self._banned_users.pop(issue_id, None)
                return False

            return True
