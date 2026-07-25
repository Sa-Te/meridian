import uuid

from app.models.orm import Chunk
from app.services.guardrails.output_guardrail import (
    ConfidenceTier,
    citation_ids_are_valid,
    classify_retrieval_confidence,
)
from app.services.retrieval import RetrievedChunk


def _chunk() -> Chunk:
    return Chunk(
        meeting_id=uuid.uuid4(),
        speaker="Alice",
        start_ts=0,
        end_ts=10,
        text="hello",
        chunk_index=0,
    )


def _retrieved(vector_score: float | None, text_score: float | None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=_chunk(), fused_score=0.0, vector_score=vector_score, text_score=text_score
    )


# --- citation_ids_are_valid ---


def test_citation_ids_are_valid_accepts_a_subset_of_valid_ids() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()

    assert citation_ids_are_valid([a], {a, b}) is True


def test_citation_ids_are_valid_rejects_empty_citations() -> None:
    assert citation_ids_are_valid([], {uuid.uuid4()}) is False


def test_citation_ids_are_valid_rejects_an_id_outside_the_valid_set() -> None:
    valid_id = uuid.uuid4()
    hallucinated_id = uuid.uuid4()

    assert citation_ids_are_valid([valid_id, hallucinated_id], {valid_id}) is False


def test_citation_ids_are_valid_works_for_a_single_source_chunk_id() -> None:
    """Extraction's per-item check: citation_ids_are_valid([source_chunk_id], valid_ids)."""
    valid_id = uuid.uuid4()

    assert citation_ids_are_valid([valid_id], {valid_id}) is True
    assert citation_ids_are_valid([uuid.uuid4()], {valid_id}) is False


# --- classify_retrieval_confidence ---


def _classify(retrieved: list[RetrievedChunk]) -> ConfidenceTier:
    return classify_retrieval_confidence(retrieved, threshold=0.3, low_confidence_floor=0.15)


def test_no_retrieved_chunks_declines() -> None:
    assert _classify([]) is ConfidenceTier.DECLINE


def test_a_real_full_text_match_is_confident_regardless_of_vector_score() -> None:
    """text_score is only ever populated when Postgres's @@ operator found a
    genuine lexical match -- its presence alone is enough, independent of
    the (possibly weak or meaningless, e.g. from a fake embedding) vector
    signal.
    """
    retrieved = [_retrieved(vector_score=0.01, text_score=0.05)]

    assert _classify(retrieved) is ConfidenceTier.CONFIDENT


def test_high_raw_vector_score_is_confident_with_no_text_match() -> None:
    retrieved = [_retrieved(vector_score=0.5, text_score=None)]

    assert _classify(retrieved) is ConfidenceTier.CONFIDENT


def test_vector_score_below_the_floor_declines() -> None:
    retrieved = [_retrieved(vector_score=0.1, text_score=None)]

    assert _classify(retrieved) is ConfidenceTier.DECLINE


def test_vector_score_between_floor_and_threshold_is_low_confidence() -> None:
    retrieved = [_retrieved(vector_score=0.2, text_score=None)]

    assert _classify(retrieved) is ConfidenceTier.LOW_CONFIDENCE


def test_vector_score_exactly_at_the_floor_is_low_confidence() -> None:
    retrieved = [_retrieved(vector_score=0.15, text_score=None)]

    assert _classify(retrieved) is ConfidenceTier.LOW_CONFIDENCE


def test_vector_score_exactly_at_threshold_is_confident() -> None:
    retrieved = [_retrieved(vector_score=0.3, text_score=None)]

    assert _classify(retrieved) is ConfidenceTier.CONFIDENT


def test_best_of_several_candidates_determines_the_outcome() -> None:
    retrieved = [
        _retrieved(vector_score=0.05, text_score=None),
        _retrieved(vector_score=0.9, text_score=None),
        _retrieved(vector_score=0.1, text_score=None),
    ]

    assert _classify(retrieved) is ConfidenceTier.CONFIDENT
