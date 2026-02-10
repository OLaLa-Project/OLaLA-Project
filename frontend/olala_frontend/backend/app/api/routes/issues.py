from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import ChatRepository
from app.db.session import get_session
from app.services.runtime import realtime_manager

router = APIRouter(tags=["issues"])


@router.get("/issues/today")
async def get_today_issue(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    issue = await ChatRepository.ensure_today_issue(session)

    total_participants = await ChatRepository.count_distinct_participants(
        session,
        issue.id,
    )
    online_participants = await realtime_manager.room_size(issue.id)
    participant_count = max(total_participants, online_participants)

    return {
        "id": issue.id,
        "title": issue.title,
        "summary": issue.summary,
        "content": issue.content,
        "category": issue.category,
        "participantCount": participant_count,
        "publishedAt": issue.published_at.isoformat(),
    }
