import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.db.repository import ChatRepository
from app.db.session import AsyncSessionLocal, get_session
from app.services.realtime import WSConnection
from app.services.runtime import event_bus, realtime_manager

router = APIRouter(tags=["chat"])


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _message_to_payload(
    message: Any,
    reaction_count: int,
    is_reacted_by_me: bool = False,
) -> dict[str, object]:
    return {
        "id": message.id,
        "issueId": message.issue_id,
        "userId": message.user_id,
        "username": message.username,
        "content": message.content,
        "timestamp": message.created_at.isoformat(),
        "reactionCount": reaction_count,
        "isReactedByMe": is_reacted_by_me,
    }


async def _publish_or_local(
    event: dict[str, object],
    fallback: Any,
) -> None:
    published = await event_bus.publish(event)
    if published:
        return
    await fallback(event)


async def _broadcast_presence(issue_id: str) -> None:
    event = {
        "type": "presence",
        "issueId": issue_id,
        "onlineCount": await realtime_manager.room_size(issue_id),
        "serverAt": _now_utc_iso(),
    }
    await _publish_or_local(
        event,
        lambda payload: realtime_manager.broadcast(issue_id, payload),
    )


async def _broadcast_reaction_updated(
    issue_id: str,
    message_id: str,
    count: int,
    server_at: str,
) -> None:
    connections = await realtime_manager.room_connections(issue_id)
    if not connections:
        return

    user_ids = [connection.user_id for connection in connections if connection.user_id]
    async with AsyncSessionLocal() as session:
        reacted_users = await ChatRepository.users_who_reacted(
            session,
            message_id,
            [user_id for user_id in user_ids if user_id is not None],
        )

    for connection in connections:
        is_reacted = (
            connection.user_id in reacted_users if connection.user_id else False
        )
        await realtime_manager.send_json(
            connection,
            {
                "type": "reaction.updated",
                "issueId": issue_id,
                "messageId": message_id,
                "count": count,
                "isReactedByMe": is_reacted,
                "serverAt": server_at,
            },
        )


async def handle_bus_event(event: dict[str, Any]) -> None:
    event_type = str(event.get("type") or "")

    if event_type == "message.created":
        issue_id = str(event.get("issueId") or "")
        if issue_id:
            await realtime_manager.broadcast(issue_id, event)
        return

    if event_type == "presence":
        issue_id = str(event.get("issueId") or "")
        if issue_id:
            await realtime_manager.broadcast(issue_id, event)
        return

    if event_type == "reaction.updated":
        issue_id = str(event.get("issueId") or "")
        message_id = str(event.get("messageId") or "")
        count = int(event.get("count") or 0)
        server_at = str(event.get("serverAt") or _now_utc_iso())
        if issue_id and message_id:
            await _broadcast_reaction_updated(issue_id, message_id, count, server_at)
        return

    if event_type == "message.deleted":
        issue_id = str(event.get("issueId") or "")
        if issue_id:
            await realtime_manager.broadcast(issue_id, event)
        return


@router.get("/chat/messages/{issue_id}")
async def get_chat_history(
    issue_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str | None = Query(default=None, alias="userId"),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    rows = await ChatRepository.list_messages(
        session,
        issue_id,
        limit,
        user_id=user_id,
    )

    result: list[dict[str, object]] = []
    for row in rows:
        message = row["message"]
        reaction_count = int(row["reaction_count"])
        is_reacted_by_me = bool(row["is_reacted_by_me"])
        result.append(
            _message_to_payload(
                message,
                reaction_count=reaction_count,
                is_reacted_by_me=is_reacted_by_me,
            ),
        )

    return result


@router.websocket("/chat/{issue_id}")
async def chat_websocket(websocket: WebSocket, issue_id: str) -> None:
    connection = await realtime_manager.connect(issue_id, websocket)
    await _broadcast_presence(issue_id)

    try:
        while True:
            raw_text = await websocket.receive_text()
            payload = _decode_payload(raw_text)
            if payload is None:
                await realtime_manager.send_json(
                    connection,
                    {
                        "type": "error",
                        "issueId": issue_id,
                        "message": "Invalid payload",
                    },
                )
                continue

            event_type = str(payload.get("type") or "")
            if event_type == "join":
                await _handle_join(connection, payload)
                continue

            if event_type == "message.create":
                await _handle_message_create(connection, payload)
                continue

            if event_type == "reaction.toggle":
                await _handle_reaction_toggle(connection, payload)
                continue

            if event_type == "message.delete":
                await _handle_message_delete(connection, payload)
                continue

            if event_type == "user.kick":
                await _handle_user_kick(connection, payload)
                continue

            await realtime_manager.send_json(
                connection,
                {
                    "type": "error",
                    "issueId": issue_id,
                    "message": f"Unknown event type: {event_type}",
                },
            )
    except WebSocketDisconnect:
        pass
    finally:
        await realtime_manager.disconnect(connection)
        await _broadcast_presence(issue_id)


async def _handle_join(connection: WSConnection, payload: dict[str, Any]) -> None:
    user_id = _clean_string(payload.get("userId"))
    nickname = _clean_string(payload.get("nickname"))

    # Check if user is banned
    if user_id and await realtime_manager.is_banned(connection.issue_id, user_id):
        await realtime_manager.send_json(
            connection,
            {
                "type": "error",
                "issueId": connection.issue_id,
                "message": "You are temporarily banned from this chat room",
            },
        )
        try:
            await connection.websocket.close(code=4003, reason="banned")
        except Exception:
            pass
        return

    await realtime_manager.update_identity(connection, user_id, nickname)
    await _broadcast_presence(connection.issue_id)


async def _handle_message_create(
    connection: WSConnection,
    payload: dict[str, Any],
) -> None:
    issue_id = connection.issue_id
    client_id = _clean_string(payload.get("clientId"))
    user_id = _clean_string(payload.get("userId")) or connection.user_id
    nickname = _clean_string(payload.get("nickname")) or connection.nickname
    content = (_clean_string(payload.get("content")) or "").strip()

    if not user_id or not nickname or not content:
        await realtime_manager.send_json(
            connection,
            {
                "type": "error",
                "issueId": issue_id,
                "message": "Invalid message payload",
            },
        )
        return

    if len(content) > settings.max_message_length:
        await realtime_manager.send_json(
            connection,
            {
                "type": "error",
                "issueId": issue_id,
                "message": f"Message is too long (max {settings.max_message_length})",
            },
        )
        return

    sent_at = _parse_iso_datetime(payload.get("sentAt"))

    async with AsyncSessionLocal() as session:
        message, created = await ChatRepository.create_message(
            session,
            issue_id=issue_id,
            user_id=user_id,
            username=nickname,
            content=content,
            client_id=client_id,
            sent_at=sent_at,
        )

    timestamp = message.created_at.isoformat()

    await realtime_manager.send_json(
        connection,
        {
            "type": "message.ack",
            "issueId": issue_id,
            "clientId": client_id,
            "serverId": message.id,
            "timestamp": timestamp,
            "status": "ok",
        },
    )

    if not created:
        return

    event = {
        "type": "message.created",
        "issueId": issue_id,
        "serverAt": timestamp,
        "clientId": client_id,
        "message": _message_to_payload(
            message,
            reaction_count=0,
            is_reacted_by_me=False,
        ),
    }
    await _publish_or_local(
        event,
        lambda payload: realtime_manager.broadcast(issue_id, payload),
    )


async def _handle_reaction_toggle(
    connection: WSConnection,
    payload: dict[str, Any],
) -> None:
    issue_id = connection.issue_id
    message_id = _clean_string(payload.get("messageId"))
    user_id = _clean_string(payload.get("userId")) or connection.user_id

    if not message_id or not user_id:
        await realtime_manager.send_json(
            connection,
            {
                "type": "error",
                "issueId": issue_id,
                "message": "Invalid reaction payload",
            },
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            message_issue_id, count = await ChatRepository.toggle_reaction(
                session,
                message_id,
                user_id,
            )
        except ValueError:
            await realtime_manager.send_json(
                connection,
                {
                    "type": "error",
                    "issueId": issue_id,
                    "message": "Message not found",
                },
            )
            return

    event = {
        "type": "reaction.updated",
        "issueId": message_issue_id,
        "messageId": message_id,
        "count": count,
        "serverAt": _now_utc_iso(),
    }
    await _publish_or_local(
        event,
        lambda payload: _broadcast_reaction_updated(
            message_issue_id,
            message_id,
            count,
            str(payload.get("serverAt") or _now_utc_iso()),
        ),
    )


async def _handle_message_delete(
    connection: WSConnection,
    payload: dict[str, Any],
) -> None:
    issue_id = connection.issue_id
    message_id = _clean_string(payload.get("messageId"))
    user_id = _clean_string(payload.get("userId")) or connection.user_id

    if not message_id or not user_id:
        await realtime_manager.send_json(
            connection,
            {
                "type": "error",
                "issueId": issue_id,
                "message": "Invalid delete payload",
            },
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            message_issue_id, _ = await ChatRepository.delete_message(
                session,
                message_id,
                user_id,
            )
        except ValueError as e:
            error_message = "Message not found"
            if str(e) == "unauthorized":
                error_message = "Only admins can delete messages"

            await realtime_manager.send_json(
                connection,
                {
                    "type": "error",
                    "issueId": issue_id,
                    "message": error_message,
                },
            )
            return

    # Broadcast deletion to all users in the room
    event = {
        "type": "message.deleted",
        "issueId": message_issue_id,
        "messageId": message_id,
        "serverAt": _now_utc_iso(),
    }
    await _publish_or_local(
        event,
        lambda payload: realtime_manager.broadcast(message_issue_id, payload),
    )


async def _handle_user_kick(
    connection: WSConnection,
    payload: dict[str, Any],
) -> None:
    issue_id = connection.issue_id
    target_user_id = _clean_string(payload.get("targetUserId"))
    admin_user_id = _clean_string(payload.get("userId")) or connection.user_id
    ban_duration = int(payload.get("banDuration", 10))  # Default 10 minutes

    if not target_user_id or not admin_user_id:
        await realtime_manager.send_json(
            connection,
            {
                "type": "error",
                "issueId": issue_id,
                "message": "Invalid kick payload",
            },
        )
        return

    # Only allow non-web users (admins) to kick users
    if admin_user_id.startswith("web_"):
        await realtime_manager.send_json(
            connection,
            {
                "type": "error",
                "issueId": issue_id,
                "message": "Only admins can kick users",
            },
        )
        return

    # Cannot kick admins
    if not target_user_id.startswith("web_"):
        await realtime_manager.send_json(
            connection,
            {
                "type": "error",
                "issueId": issue_id,
                "message": "Cannot kick admin users",
            },
        )
        return

    # Kick the user
    kicked_count = await realtime_manager.kick_user(
        issue_id,
        target_user_id,
        ban_duration,
    )

    if kicked_count > 0:
        # Broadcast kick notification to remaining users
        event = {
            "type": "user.kicked.notification",
            "issueId": issue_id,
            "userId": target_user_id,
            "serverAt": _now_utc_iso(),
        }
        await _publish_or_local(
            event,
            lambda payload: realtime_manager.broadcast(issue_id, payload),
        )


def _clean_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed if trimmed else None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _decode_payload(raw_text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None
    return data


def _parse_iso_datetime(value: object) -> datetime | None:
    normalized = _clean_string(value)
    if normalized is None:
        return None

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
