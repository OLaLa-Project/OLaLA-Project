from __future__ import annotations

import asyncio
import logging
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/v1", tags=["mobile"])
logger = logging.getLogger(__name__)


@dataclass(eq=False)
class RoomConnection:
    socket: WebSocket
    issue_id: str
    user_id: str | None = None
    nickname: str | None = None


_rooms: dict[str, set[RoomConnection]] = defaultdict(set)
_messages: dict[str, list[dict[str, Any]]] = defaultdict(list)
_reactions: dict[str, set[str]] = defaultdict(set)
_state_lock = asyncio.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_issue_id() -> str:
    now = datetime.now()
    return f"issue_{now.year}{now.month:02d}{now.day:02d}"


def _build_issue(participant_count: int) -> dict[str, Any]:
    now = datetime.now()
    return {
        "id": _today_issue_id(),
        "title": "오늘의 이슈: AI 규제와 산업 영향",
        "summary": "AI 규제 강화 정책과 산업 전반 영향에 대한 공개 토론 이슈입니다.",
        "content": "백엔드 연동용 기본 이슈 본문입니다. 운영 데이터 연결 시 실제 기사 본문으로 교체됩니다.",
        "category": "정치/기술",
        "participantCount": participant_count,
        "publishedAt": now.replace(hour=max(now.hour - 2, 0)).isoformat(),
    }


def _message_view(message: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    message_id = str(message["id"])
    reaction_users = _reactions.get(message_id, set())
    return {
        "id": message_id,
        "issueId": message["issueId"],
        "userId": message["userId"],
        "username": message["username"],
        "content": message["content"],
        "timestamp": message["timestamp"],
        "reactionCount": len(reaction_users),
        "isReactedByMe": bool(user_id and user_id in reaction_users),
        "isMine": False,
    }


async def _safe_send(conn: RoomConnection, payload: dict[str, Any]) -> bool:
    try:
        await conn.socket.send_json(payload)
        return True
    except Exception:
        logger.debug("socket send failed", exc_info=True)
        return False


async def _broadcast(issue_id: str, payload_builder: Callable[[RoomConnection], dict[str, Any]]) -> None:
    async with _state_lock:
        room = list(_rooms.get(issue_id, set()))

    stale: list[RoomConnection] = []
    for conn in room:
        payload = payload_builder(conn)
        ok = await _safe_send(conn, payload)
        if not ok:
            stale.append(conn)

    if stale:
        async with _state_lock:
            live = _rooms.get(issue_id)
            if live is not None:
                for conn in stale:
                    live.discard(conn)


async def _broadcast_presence(issue_id: str) -> None:
    async with _state_lock:
        online_count = len(_rooms.get(issue_id, set()))

    payload = {
        "type": "presence",
        "issueId": issue_id,
        "onlineCount": online_count,
        "serverAt": _now_iso(),
    }
    await _broadcast(issue_id, lambda _conn: payload)


@router.get("/issues/today")
async def get_today_issue() -> dict[str, Any]:
    issue_id = _today_issue_id()
    async with _state_lock:
        participant_count = len(_rooms.get(issue_id, set()))
    return _build_issue(participant_count)


@router.get("/chat/messages/{issue_id}")
async def get_chat_messages(issue_id: str, limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    async with _state_lock:
        history = list(_messages.get(issue_id, []))
    selected = history[-limit:] if len(history) > limit else history
    return [_message_view(msg) for msg in selected]


@router.websocket("/chat/{issue_id}")
async def chat_socket(websocket: WebSocket, issue_id: str) -> None:
    await websocket.accept()
    conn = RoomConnection(socket=websocket, issue_id=issue_id)

    async with _state_lock:
        _rooms[issue_id].add(conn)

    await _broadcast_presence(issue_id)

    try:
        while True:
            data = await websocket.receive_json()
            event_type = str(data.get("type", "")).strip()

            if event_type == "join":
                conn.user_id = str(data.get("userId", "")).strip() or None
                conn.nickname = str(data.get("nickname", "")).strip() or None
                await _broadcast_presence(issue_id)
                continue

            if event_type == "message.create":
                content = str(data.get("content", "")).strip()
                user_id = str(data.get("userId") or conn.user_id or "").strip()
                nickname = str(data.get("nickname") or conn.nickname or "익명").strip()
                client_id = data.get("clientId")

                if not content or not user_id:
                    await _safe_send(
                        conn,
                        {
                            "type": "error",
                            "issueId": issue_id,
                            "message": "Invalid message payload",
                        },
                    )
                    continue

                server_id = f"msg_{int(datetime.now().timestamp() * 1000)}_{random.randint(1000, 9999)}"
                timestamp = _now_iso()
                message = {
                    "id": server_id,
                    "issueId": issue_id,
                    "userId": user_id,
                    "username": nickname,
                    "content": content,
                    "timestamp": timestamp,
                }

                async with _state_lock:
                    _messages[issue_id].append(message)

                await _safe_send(
                    conn,
                    {
                        "type": "message.ack",
                        "issueId": issue_id,
                        "clientId": client_id,
                        "serverId": server_id,
                        "timestamp": timestamp,
                        "status": "ok",
                    },
                )

                await _broadcast(
                    issue_id,
                    lambda recipient: {
                        "type": "message.created",
                        "issueId": issue_id,
                        "serverAt": timestamp,
                        **({"clientId": client_id} if client_id is not None else {}),
                        "message": _message_view(message, recipient.user_id),
                    },
                )
                continue

            if event_type == "reaction.toggle":
                message_id = str(data.get("messageId", "")).strip()
                user_id = str(data.get("userId") or conn.user_id or "").strip()
                if not message_id or not user_id:
                    await _safe_send(
                        conn,
                        {
                            "type": "error",
                            "issueId": issue_id,
                            "message": "Invalid reaction payload",
                        },
                    )
                    continue

                async with _state_lock:
                    user_set = _reactions[message_id]
                    if user_id in user_set:
                        user_set.remove(user_id)
                    else:
                        user_set.add(user_id)
                    count = len(user_set)

                await _broadcast(
                    issue_id,
                    lambda recipient: {
                        "type": "reaction.updated",
                        "issueId": issue_id,
                        "messageId": message_id,
                        "count": count,
                        "isReactedByMe": bool(recipient.user_id and recipient.user_id in _reactions[message_id]),
                        "serverAt": _now_iso(),
                    },
                )
                continue

            await _safe_send(
                conn,
                {
                    "type": "error",
                    "issueId": issue_id,
                    "message": f"Unknown event type: {event_type}",
                },
            )

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("chat websocket failed")
    finally:
        async with _state_lock:
            room = _rooms.get(issue_id)
            if room is not None:
                room.discard(conn)
                if not room:
                    _rooms.pop(issue_id, None)
        await _broadcast_presence(issue_id)
