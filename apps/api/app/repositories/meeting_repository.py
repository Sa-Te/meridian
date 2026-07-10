from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.orm import Meeting


class MeetingRepository:
    """Database access for the Meeting aggregate (a Meeting and its Chunks,
    Decisions, and ActionItems). One repository per aggregate root, per
    CLAUDE.md Section 5 -- Decision/ActionItem never get their own
    repository, they're only ever reached through their owning Meeting.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, meeting: Meeting) -> Meeting:
        """Persist a Meeting, cascading to any Chunks already attached to it."""
        self._session.add(meeting)
        await self._session.commit()
        await self._session.refresh(meeting, attribute_names=["chunks"])
        return meeting

    async def get_by_id(self, meeting_id: UUID) -> Meeting | None:
        result = await self._session.execute(
            select(Meeting).where(Meeting.id == meeting_id).options(selectinload(Meeting.chunks))
        )
        return result.scalar_one_or_none()
