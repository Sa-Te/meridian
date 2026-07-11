"""Cross-meeting ActionItem queries for the global GET /action-items
endpoint. Same reasoning as ChunkRepository (ADR-0007): a read that spans
the Meeting aggregate boundary doesn't fit inside MeetingRepository, whose
"one repository per aggregate root" scope is about write/consistency
boundaries, not read queries. See docs/adr/0008.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ActionItem, ActionItemStatus


class ActionItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(
        self, *, status: ActionItemStatus | None = None, owner: str | None = None
    ) -> list[ActionItem]:
        stmt = select(ActionItem)
        if status is not None:
            stmt = stmt.where(ActionItem.status == status)
        if owner is not None:
            stmt = stmt.where(ActionItem.owner == owner)
        stmt = stmt.order_by(ActionItem.created_at)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())
