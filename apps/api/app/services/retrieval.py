"""Hybrid chunk retrieval: pgvector cosine similarity + Postgres full-text
search, fused with a simple weighted score. See docs/adr/0007.
"""

from dataclasses import dataclass
from uuid import UUID

from app.models.orm import Chunk
from app.repositories.chunk_repository import ChunkRepository


@dataclass(frozen=True)
class CandidateScore:
    """Raw, unnormalized retrieval signal(s) for one chunk, keyed by id.

    Either score may be absent: a chunk retrieved only by vector search has
    no text_score, and a chunk retrieved only by full-text search has no
    vector_score.
    """

    chunk_id: UUID
    vector_score: float | None
    text_score: float | None


@dataclass(frozen=True)
class FusedResult:
    """A chunk_id ranked by its fused score."""

    chunk_id: UUID
    fused_score: float


@dataclass(frozen=True)
class RetrievedChunk:
    """A fully-hydrated Chunk plus its fusion score, ready for generation."""

    chunk: Chunk
    fused_score: float


def _normalize(raw_scores: dict[UUID, float]) -> dict[UUID, float]:
    """Min-max normalize to [0, 1] so cosine similarity and ts_rank -- which
    live on unrelated scales -- can be weighted-summed meaningfully. A
    single distinct value (including a one-candidate input) normalizes to
    1.0 for every key rather than dividing by zero.
    """
    if not raw_scores:
        return {}
    low = min(raw_scores.values())
    high = max(raw_scores.values())
    if high == low:
        return dict.fromkeys(raw_scores, 1.0)
    span = high - low
    return {key: (value - low) / span for key, value in raw_scores.items()}


def fuse_scores(
    candidates: list[CandidateScore],
    *,
    vector_weight: float,
    text_weight: float,
) -> list[FusedResult]:
    """Combine vector-similarity and full-text scores into one ranking.

    Each score is independently min-max normalized across `candidates`
    before weighting, since raw cosine similarity (roughly [0, 1] for
    normalized embeddings) and raw ts_rank (an unbounded, corpus-dependent
    float) aren't comparable on their own scales. A chunk missing one
    signal (only matched by the other search method) contributes 0 for the
    missing side rather than being excluded from the ranking.
    """
    vector_scores = {c.chunk_id: c.vector_score for c in candidates if c.vector_score is not None}
    text_scores = {c.chunk_id: c.text_score for c in candidates if c.text_score is not None}
    normalized_vector = _normalize(vector_scores)
    normalized_text = _normalize(text_scores)

    results = [
        FusedResult(
            chunk_id=candidate.chunk_id,
            fused_score=(
                vector_weight * normalized_vector.get(candidate.chunk_id, 0.0)
                + text_weight * normalized_text.get(candidate.chunk_id, 0.0)
            ),
        )
        for candidate in candidates
    ]
    results.sort(key=lambda result: result.fused_score, reverse=True)
    return results


async def hybrid_search(
    *,
    query_text: str,
    query_embedding: list[float],
    chunk_repository: ChunkRepository,
    meeting_id: UUID | None,
    top_k: int,
    candidate_pool_size: int,
    vector_weight: float,
    text_weight: float,
) -> list[RetrievedChunk]:
    """Retrieve the top_k chunks for a question via hybrid search.

    Fetches candidate_pool_size candidates from each of vector search and
    full-text search, fuses their scores with fuse_scores, and returns the
    top_k fully-hydrated chunks in fused-score order.
    """
    vector_candidates = await chunk_repository.vector_candidates(
        query_embedding, meeting_id=meeting_id, limit=candidate_pool_size
    )
    text_candidates = await chunk_repository.text_candidates(
        query_text, meeting_id=meeting_id, limit=candidate_pool_size
    )

    vector_scores = {candidate.chunk.id: candidate.vector_score for candidate in vector_candidates}
    text_scores = {candidate.chunk.id: candidate.text_score for candidate in text_candidates}
    chunks_by_id: dict[UUID, Chunk] = {
        candidate.chunk.id: candidate.chunk for candidate in [*vector_candidates, *text_candidates]
    }

    candidate_scores = [
        CandidateScore(
            chunk_id=chunk_id,
            vector_score=vector_scores.get(chunk_id),
            text_score=text_scores.get(chunk_id),
        )
        for chunk_id in chunks_by_id
    ]
    fused = fuse_scores(candidate_scores, vector_weight=vector_weight, text_weight=text_weight)

    return [
        RetrievedChunk(chunk=chunks_by_id[result.chunk_id], fused_score=result.fused_score)
        for result in fused[:top_k]
    ]
