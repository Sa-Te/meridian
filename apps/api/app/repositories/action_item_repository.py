"""Cross-meeting ActionItem queries for the global GET /action-items
endpoint. Same reasoning as ChunkRepository (ADR-0007): a read that spans
the Meeting aggregate boundary doesn't fit inside MeetingRepository, whose
"one repository per aggregate root" scope is about write/consistency
boundaries, not read queries. See docs/adr/0008.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.orm import ActionItem, ActionItemStatus


class ActionItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(
        self, *, status: ActionItemStatus | None = None, owner: str | None = None
    ) -> list[ActionItem]:
        # Eager-loads source_chunk so the router can build each item's
        # source_citation (Phase 7) without a lazy-load, which isn't safe
        # from an async context -- same reasoning as MeetingRepository's
        # eager-loaded relationships.
        stmt = select(ActionItem).options(selectinload(ActionItem.source_chunk))
        if status is not None:
            stmt = stmt.where(ActionItem.status == status)
        if owner is not None:
            stmt = stmt.where(ActionItem.owner == owner)
        stmt = stmt.order_by(ActionItem.created_at)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())
