import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

from .models import ChatMessage, Issue, MessageReaction


class ChatRepository:
    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _issue_id_for_today(timezone_name: str) -> str:
        now = datetime.now(ZoneInfo(timezone_name))
        return f"issue_{now.year:04d}{now.month:02d}{now.day:02d}"

    @classmethod
    async def ensure_today_issue(cls, session: AsyncSession) -> Issue:
        issue_id = cls._issue_id_for_today(settings.issue_timezone)
        return await cls.ensure_issue(session, issue_id)

    @classmethod
    async def ensure_issue(cls, session: AsyncSession, issue_id: str) -> Issue:
        issue = await session.get(Issue, issue_id)
        if issue:
            return issue

        now = cls._now_utc()
        issue = Issue(
            id=issue_id,
            title="2025년 AI 윤리 규제안, 국회 본회의 통과",
            summary=(
                "인공지능 개발 및 활용에 대한 윤리적 기준을 명시한 법안이 "
                "국회를 통과했습니다. 이번 법안은 AI 시스템의 투명성, 설명 가능성, "
                "공정성을 강화하는 내용을 담고 있습니다."
            ),
            content=(
                "FastAPI 백엔드 인프라 기본 기사 본문입니다. "
                "운영 환경에서는 뉴스 수집/에디터 파이프라인과 연결해 실제 본문을 제공합니다."
            ),
            category=settings.default_issue_category,
            published_at=now - timedelta(hours=2),
        )
        session.add(issue)

        try:
            await session.commit()
            await session.refresh(issue)
            return issue
        except IntegrityError:
            await session.rollback()
            existing = await session.get(Issue, issue_id)
            if existing is None:
                raise
            return existing

    @classmethod
    async def count_distinct_participants(
        cls,
        session: AsyncSession,
        issue_id: str,
    ) -> int:
        stmt = select(func.count(distinct(ChatMessage.user_id))).where(
            ChatMessage.issue_id == issue_id,
        )
        count = await session.scalar(stmt)
        return int(count or 0)

    @classmethod
    async def list_messages(
        cls,
        session: AsyncSession,
        issue_id: str,
        limit: int,
        user_id: str | None = None,
    ) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, settings.max_chat_history_limit))

        reaction_subquery = (
            select(
                MessageReaction.message_id.label("message_id"),
                func.count(MessageReaction.user_id).label("reaction_count"),
            )
            .group_by(MessageReaction.message_id)
            .subquery()
        )

        stmt = (
            select(
                ChatMessage,
                func.coalesce(reaction_subquery.c.reaction_count, 0).label(
                    "reaction_count",
                ),
            )
            .outerjoin(
                reaction_subquery,
                reaction_subquery.c.message_id == ChatMessage.id,
            )
            .where(ChatMessage.issue_id == issue_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(safe_limit)
        )

        rows = (await session.execute(stmt)).all()
        rows = list(reversed(rows))

        reacted_ids: set[str] = set()
        if user_id and rows:
            message_ids = [message.id for message, _ in rows]
            reacted_stmt = select(MessageReaction.message_id).where(
                MessageReaction.user_id == user_id,
                MessageReaction.message_id.in_(message_ids),
            )
            reacted_ids = set((await session.execute(reacted_stmt)).scalars().all())

        result: list[dict[str, object]] = []
        for message, reaction_count in rows:
            result.append(
                {
                    "message": message,
                    "reaction_count": int(reaction_count or 0),
                    "is_reacted_by_me": message.id in reacted_ids,
                },
            )
        return result

    @classmethod
    async def create_message(
        cls,
        session: AsyncSession,
        issue_id: str,
        user_id: str,
        username: str,
        content: str,
        client_id: str | None,
        sent_at: datetime | None,
    ) -> tuple[ChatMessage, bool]:
        await cls.ensure_issue(session, issue_id)

        if client_id:
            existing_stmt = select(ChatMessage).where(
                ChatMessage.issue_id == issue_id,
                ChatMessage.user_id == user_id,
                ChatMessage.client_id == client_id,
            )
            existing = (await session.execute(existing_stmt)).scalar_one_or_none()
            if existing:
                return existing, False

        message_id = f"msg_{int(cls._now_utc().timestamp() * 1000)}_{secrets.randbelow(10000):04d}"
        message = ChatMessage(
            id=message_id,
            issue_id=issue_id,
            client_id=client_id,
            user_id=user_id,
            username=username,
            content=content,
            created_at=sent_at or cls._now_utc(),
        )
        session.add(message)

        try:
            await session.commit()
            await session.refresh(message)
            return message, True
        except IntegrityError:
            await session.rollback()
            if not client_id:
                raise
            existing_stmt = select(ChatMessage).where(
                ChatMessage.issue_id == issue_id,
                ChatMessage.user_id == user_id,
                ChatMessage.client_id == client_id,
            )
            existing = (await session.execute(existing_stmt)).scalar_one_or_none()
            if existing is None:
                raise
            return existing, False

    @classmethod
    async def toggle_reaction(
        cls,
        session: AsyncSession,
        message_id: str,
        user_id: str,
    ) -> tuple[str, int]:
        message = await session.get(ChatMessage, message_id)
        if message is None:
            raise ValueError("message_not_found")

        existing_stmt = select(MessageReaction).where(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user_id,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()

        if existing is None:
            session.add(MessageReaction(message_id=message_id, user_id=user_id))
        else:
            await session.execute(
                delete(MessageReaction).where(
                    MessageReaction.message_id == message_id,
                    MessageReaction.user_id == user_id,
                ),
            )

        await session.commit()

        count_stmt = select(func.count(MessageReaction.user_id)).where(
            MessageReaction.message_id == message_id,
        )
        count = await session.scalar(count_stmt)
        return message.issue_id, int(count or 0)

    @classmethod
    async def users_who_reacted(
        cls,
        session: AsyncSession,
        message_id: str,
        user_ids: list[str],
    ) -> set[str]:
        if not user_ids:
            return set()

        stmt = select(MessageReaction.user_id).where(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id.in_(user_ids),
        )
        return set((await session.execute(stmt)).scalars().all())

    @classmethod
    async def delete_message(
        cls,
        session: AsyncSession,
        message_id: str,
        user_id: str,
    ) -> tuple[str, bool]:
        """
        Delete a message. Only non-web users (admins) can delete messages.

        Returns:
            tuple[str, bool]: (issue_id, was_deleted)
        """
        message = await session.get(ChatMessage, message_id)
        if message is None:
            raise ValueError("message_not_found")

        # Only allow non-web users (admins) to delete messages
        if user_id.startswith("web_"):
            raise ValueError("unauthorized")

        issue_id = message.issue_id

        # Delete associated reactions first
        await session.execute(
            delete(MessageReaction).where(
                MessageReaction.message_id == message_id,
            ),
        )

        # Delete the message
        await session.execute(
            delete(ChatMessage).where(
                ChatMessage.id == message_id,
            ),
        )

        await session.commit()
        return issue_id, True
