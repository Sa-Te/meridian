from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.orm import ActionItem, Decision, Meeting


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

    async def add_extractions(
        self,
        meeting: Meeting,
        *,
        decisions: Sequence[Decision],
        action_items: Sequence[ActionItem],
    ) -> Meeting:
        """Attach Phase 4 extraction output to an already-persisted Meeting.

        Sets meeting_id directly on each child and adds them individually,
        rather than assigning meeting.decisions/meeting.action_items --
        assigning a relationship collection makes the ORM lazy-load the
        current collection first to diff against, which isn't safe from an
        async context without AsyncAttrs. See docs/adr/0008.
        """
        for decision in decisions:
            decision.meeting_id = meeting.id
        for action_item in action_items:
            action_item.meeting_id = meeting.id
        self._session.add_all([*decisions, *action_items])
        await self._session.commit()
        await self._session.refresh(meeting, attribute_names=["decisions", "action_items"])
        return meeting

    async def get_by_id(self, meeting_id: UUID) -> Meeting | None:
        result = await self._session.execute(
            select(Meeting)
            .where(Meeting.id == meeting_id)
            .options(
                selectinload(Meeting.chunks),
                selectinload(Meeting.decisions),
                selectinload(Meeting.action_items),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_source_filename(self, source_filename: str) -> Meeting | None:
        """Look up a Meeting by the transcript filename it was ingested from.

        Used by eval/run_eval.py (see docs/adr/0009) to make repeated local
        eval runs idempotent -- a transcript already ingested from a prior
        run is reused rather than re-ingested into a duplicate Meeting.
        source_filename has no uniqueness constraint at the schema level
        (re-ingesting the same file twice is a valid, if unusual, action
        elsewhere in the app), so this returns the first match rather than
        asserting uniqueness.
        """
        result = await self._session.execute(
            select(Meeting)
            .where(Meeting.source_filename == source_filename)
            .options(
                selectinload(Meeting.chunks),
                selectinload(Meeting.decisions),
                selectinload(Meeting.action_items),
            )
        )
        return result.scalars().first()
