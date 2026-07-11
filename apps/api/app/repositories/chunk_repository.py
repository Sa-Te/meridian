"""Read access for hybrid chunk retrieval (cosine similarity + full-text
search). See docs/adr/0007.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chunk


@dataclass(frozen=True)
class ChunkCandidate:
    """A Chunk plus the raw score from whichever single search method
    (vector or full-text) produced this row. The other score is always
    None here -- callers merge candidates from both methods before fusion.
    """

    chunk: Chunk
    vector_score: float | None
    text_score: float | None


class ChunkRepository:
    """Chunk search queries, spanning the Meeting aggregate boundary.

    Retrieval reads chunks across meetings (the global /ask endpoint) or
    scoped to one -- a read-query shape that doesn't fit "one repository
    per aggregate root" (CLAUDE.md Section 5, which governs write/aggregate
    consistency boundaries, not cross-aggregate search). See ADR-0007 for
    why this is its own repository rather than a method on
    MeetingRepository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def vector_candidates(
        self, query_embedding: list[float], *, meeting_id: UUID | None, limit: int
    ) -> list[ChunkCandidate]:
        """Top `limit` chunks by cosine similarity to query_embedding,
        highest similarity first. Chunks without an embedding are excluded.
        """
        distance_expr = Chunk.embedding.cosine_distance(query_embedding)
        stmt = select(Chunk, distance_expr.label("distance")).where(Chunk.embedding.is_not(None))
        if meeting_id is not None:
            stmt = stmt.where(Chunk.meeting_id == meeting_id)
        stmt = stmt.order_by(distance_expr).limit(limit)

        result = await self._session.execute(stmt)
        return [
            ChunkCandidate(chunk=chunk, vector_score=1.0 - distance_value, text_score=None)
            for chunk, distance_value in result.all()
        ]

    async def text_candidates(
        self, query_text: str, *, meeting_id: UUID | None, limit: int
    ) -> list[ChunkCandidate]:
        """Top `limit` chunks whose search_vector matches query_text, by
        ts_rank, highest rank first. Unlike vector search, chunks with no
        match are excluded entirely rather than padded to `limit`.
        """
        tsquery = func.plainto_tsquery("english", query_text)
        rank_expr = func.ts_rank(Chunk.search_vector, tsquery).label("rank")
        stmt = select(Chunk, rank_expr).where(Chunk.search_vector.op("@@")(tsquery))
        if meeting_id is not None:
            stmt = stmt.where(Chunk.meeting_id == meeting_id)
        stmt = stmt.order_by(rank_expr.desc()).limit(limit)

        result = await self._session.execute(stmt)
        return [
            ChunkCandidate(chunk=chunk, vector_score=None, text_score=rank_value)
            for chunk, rank_value in result.all()
        ]
