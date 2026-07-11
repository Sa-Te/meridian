"""Output guardrails: citation enforcement (generalized from ADR-0007's
Phase 3 implementation so answer generation and structured extraction share
one check) plus a retrieval confidence threshold below which the ask flow
declines to answer rather than guessing. See docs/adr/0008.
"""

from collections.abc import Collection, Sequence
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.services.retrieval import RetrievedChunk


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


def passes_retrieval_confidence(retrieved: Sequence["RetrievedChunk"], *, threshold: float) -> bool:
    """True if the retrieved set is trustworthy enough to attempt an answer.

    Declines (returns False) only when nothing in the retrieved set is
    grounded: no chunk has an actual full-text match, and no chunk's raw
    vector similarity meets `threshold`.

    This deliberately uses each chunk's *raw* vector_score, not the fused,
    min-max-normalized score from app/services/retrieval.py. Normalization
    always maps the best candidate in a non-empty pool to 1.0 -- vector
    search returns its nearest neighbors regardless of whether any of them
    are truly relevant, so a normalized score can't distinguish a genuine
    semantic match from "the least-bad candidate in an irrelevant pool."
    Raw cosine similarity lives on an absolute scale instead. Full-text
    presence needs no threshold at all: Postgres's `@@` match operator
    already only returns a text_score when a real lexical match exists, so
    its mere presence -- at any value -- is a meaningful signal on its own.
    """
    if not retrieved:
        return False
    if any(candidate.text_score is not None for candidate in retrieved):
        return True
    return any(
        candidate.vector_score is not None and candidate.vector_score >= threshold
        for candidate in retrieved
    )
