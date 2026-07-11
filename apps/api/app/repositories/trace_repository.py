"""Trace persistence and querying for GET /traces (Phase 6). A trace spans
whichever endpoint produced it (the ask flow, the ingest flow) -- a
cross-cutting concern that doesn't belong to any single aggregate, the same
reasoning ChunkRepository/ActionItemRepository already established for a
read that doesn't fit inside one aggregate's own repository. See
docs/adr/0010.
"""

from datetime import UTC, datetime, time, timedelta
from datetime import date as date_type
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Trace, TraceOutcome


class TraceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, trace: Trace) -> Trace:
        self._session.add(trace)
        await self._session.commit()
        await self._session.refresh(trace)
        return trace

    async def get_by_id(self, trace_id: UUID) -> Trace | None:
        result = await self._session.execute(select(Trace).where(Trace.id == trace_id))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        endpoint: str | None = None,
        outcome: TraceOutcome | None = None,
        on_date: date_type | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[Trace], int]:
        """Newest-first page of traces matching the given filters, plus the
        total count matching those same filters (for pagination metadata).
        """
        stmt = select(Trace)
        if endpoint is not None:
            stmt = stmt.where(Trace.endpoint == endpoint)
        if outcome is not None:
            stmt = stmt.where(Trace.outcome == outcome)
        if on_date is not None:
            day_start = datetime.combine(on_date, time.min, tzinfo=UTC)
            day_end = day_start + timedelta(days=1)
            stmt = stmt.where(Trace.created_at >= day_start, Trace.created_at < day_end)

        total = (
            await self._session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()

        stmt = stmt.order_by(Trace.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total
