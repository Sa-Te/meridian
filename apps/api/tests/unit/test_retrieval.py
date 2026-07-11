import uuid

from app.services.retrieval import CandidateScore, fuse_scores

_A = uuid.uuid4()
_B = uuid.uuid4()
_C = uuid.uuid4()


def test_empty_candidate_list_returns_empty_result() -> None:
    assert fuse_scores([], vector_weight=0.6, text_weight=0.4) == []


def test_single_candidate_normalizes_without_dividing_by_zero() -> None:
    candidates = [CandidateScore(chunk_id=_A, vector_score=0.42, text_score=0.1)]

    results = fuse_scores(candidates, vector_weight=0.6, text_weight=0.4)

    assert len(results) == 1
    assert results[0].chunk_id == _A
    assert results[0].fused_score == 1.0


def test_higher_vector_score_ranks_first_when_text_scores_tie() -> None:
    candidates = [
        CandidateScore(chunk_id=_A, vector_score=0.9, text_score=0.5),
        CandidateScore(chunk_id=_B, vector_score=0.1, text_score=0.5),
    ]

    results = fuse_scores(candidates, vector_weight=0.6, text_weight=0.4)

    assert [result.chunk_id for result in results] == [_A, _B]


def test_missing_vector_score_contributes_zero_not_exclusion() -> None:
    """A chunk found only by full-text search (no vector_score) is still
    ranked, using only its normalized text_score."""
    candidates = [
        CandidateScore(chunk_id=_A, vector_score=0.8, text_score=None),
        CandidateScore(chunk_id=_B, vector_score=None, text_score=1.0),
    ]

    results = fuse_scores(candidates, vector_weight=0.5, text_weight=0.5)

    by_id = {result.chunk_id: result.fused_score for result in results}
    # _A: normalized vector_score of the only vector candidate -> 1.0, no text signal.
    assert by_id[_A] == 0.5 * 1.0
    # _B: normalized text_score of the only text candidate -> 1.0, no vector signal.
    assert by_id[_B] == 0.5 * 1.0


def test_missing_text_score_contributes_zero() -> None:
    candidates = [
        CandidateScore(chunk_id=_A, vector_score=0.5, text_score=None),
    ]

    results = fuse_scores(candidates, vector_weight=0.6, text_weight=0.4)

    assert results[0].fused_score == 0.6 * 1.0


def test_zero_weight_on_one_signal_ranks_purely_by_the_other() -> None:
    candidates = [
        CandidateScore(chunk_id=_A, vector_score=0.1, text_score=0.9),
        CandidateScore(chunk_id=_B, vector_score=0.9, text_score=0.1),
    ]

    results = fuse_scores(candidates, vector_weight=1.0, text_weight=0.0)

    assert [result.chunk_id for result in results] == [_B, _A]


def test_tied_fused_scores_preserve_original_relative_order() -> None:
    """All three candidates have identical vector and text scores, so every
    signal normalizes to 1.0 for all of them -- a three-way tie. Python's
    sort is stable, so the original input order should be preserved.
    """
    candidates = [
        CandidateScore(chunk_id=_A, vector_score=0.5, text_score=0.5),
        CandidateScore(chunk_id=_B, vector_score=0.5, text_score=0.5),
        CandidateScore(chunk_id=_C, vector_score=0.5, text_score=0.5),
    ]

    results = fuse_scores(candidates, vector_weight=0.6, text_weight=0.4)

    assert [result.chunk_id for result in results] == [_A, _B, _C]
    assert all(result.fused_score == 1.0 for result in results)


def test_weighted_combination_can_reorder_relative_to_either_signal_alone() -> None:
    """_A has the best vector score but the worst text score; _B is the
    reverse. With balanced weights, the candidate with the stronger overall
    normalized combination should win."""
    candidates = [
        CandidateScore(chunk_id=_A, vector_score=1.0, text_score=0.0),
        CandidateScore(chunk_id=_B, vector_score=0.0, text_score=1.0),
        CandidateScore(chunk_id=_C, vector_score=0.6, text_score=0.6),
    ]

    results = fuse_scores(candidates, vector_weight=0.5, text_weight=0.5)

    by_id = {result.chunk_id: result.fused_score for result in results}
    assert by_id[_A] == 0.5
    assert by_id[_B] == 0.5
    assert by_id[_C] == 0.5 * 0.6 + 0.5 * 0.6
    assert results[0].chunk_id == _C
