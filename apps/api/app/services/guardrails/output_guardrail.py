"""Output guardrails: citation enforcement (generalized from ADR-0007's
Phase 3 implementation so answer generation and structured extraction share
one check) plus a retrieval confidence threshold below which the ask flow
declines to answer rather than guessing. See docs/adr/0008.
"""

from collections.abc import Collection, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.services.retrieval import RetrievedChunk


class ConfidenceTier(StrEnum):
    DECLINE = "decline"
    LOW_CONFIDENCE = "low_confidence"
    CONFIDENT = "confident"


def classify_retrieval_confidence(
    retrieved: Sequence["RetrievedChunk"],
    *,
    threshold: float,
    low_confidence_floor: float,
) -> ConfidenceTier:
    """Classifies whether the retrieved set is trustworthy enough to attempt
    an answer, and if so, how confidently.

    A real full-text match is always CONFIDENT, regardless of vector score:
    Postgres's `@@` match operator only ever returns a text_score when a
    genuine lexical match exists, so its mere presence is a meaningful
    signal on its own, needing no threshold.

    Otherwise, each chunk's *raw* vector_score decides -- not the fused,
    min-max-normalized score from app/services/retrieval.py. Normalization
    always maps the best candidate in a non-empty pool to 1.0, so it can't
    distinguish a genuine semantic match from "the least-bad candidate in
    an irrelevant pool"; raw cosine similarity lives on an absolute scale
    instead. At or above `threshold` is CONFIDENT; at or above
    `low_confidence_floor` but below `threshold` is LOW_CONFIDENCE (still
    attempt an answer, but flag it); below the floor is DECLINE.
    """
    if not retrieved:
        return ConfidenceTier.DECLINE
    if any(candidate.text_score is not None for candidate in retrieved):
        return ConfidenceTier.CONFIDENT

    best_vector_score = max(
        (candidate.vector_score for candidate in retrieved if candidate.vector_score is not None),
        default=None,
    )
    if best_vector_score is None:
        return ConfidenceTier.DECLINE
    if best_vector_score >= threshold:
        return ConfidenceTier.CONFIDENT
    if best_vector_score >= low_confidence_floor:
        return ConfidenceTier.LOW_CONFIDENCE
    return ConfidenceTier.DECLINE


def citation_ids_are_valid(cited_ids: Collection[UUID], valid_ids: Collection[UUID]) -> bool:
    """True only if cited_ids is non-empty and every id in it is a member of
    valid_ids. A citation is a claim of grounding -- an empty claim (nothing
    cited) or a claim pointing outside the set of chunks actually available
    (a hallucinated or out-of-scope id) both fail it.

    Shared by app/services/answer_generation.py (a list of citations per
    answer) and app/services/extraction.py (a single source_chunk_id per
    extracted Decision/ActionItem, checked as citation_ids_are_valid(
    [source_chunk_id], valid_ids)).
    """
    valid = set(valid_ids)
    return bool(cited_ids) and set(cited_ids).issubset(valid)
