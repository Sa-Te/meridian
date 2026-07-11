import uuid

from eval.metrics import evaluate_gate, mean, precision_at_k, recall_at_k


def _uuids(n: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(n)]


def test_precision_at_k_with_no_retrieved_chunks_is_zero() -> None:
    assert precision_at_k([], {uuid.uuid4()}) == 0.0


def test_precision_at_k_counts_only_relevant_hits_among_retrieved() -> None:
    a, b, c = _uuids(3)
    retrieved = [a, b, c]
    expected = {a}

    assert precision_at_k(retrieved, expected) == 1 / 3


def test_precision_at_k_is_one_when_every_retrieved_chunk_is_relevant() -> None:
    a, b = _uuids(2)
    assert precision_at_k([a, b], {a, b}) == 1.0


def test_recall_at_k_with_empty_expected_set_is_zero() -> None:
    assert recall_at_k([uuid.uuid4()], set()) == 0.0


def test_recall_at_k_is_a_hit_rate_not_a_fraction() -> None:
    """expected_ids may hold more than one chunk id when a fact is restated
    in more than one turn -- finding any one of them is a full hit, not
    partial credit. See recall_at_k's docstring and docs/adr/0009.
    """
    a, b = _uuids(2)
    expected = {a, b}

    assert recall_at_k([a], expected) == 1.0
    assert recall_at_k([a, b], expected) == 1.0
    assert recall_at_k([uuid.uuid4()], expected) == 0.0


def test_mean_of_empty_iterable_is_zero() -> None:
    assert mean([]) == 0.0


def test_mean_computes_arithmetic_mean() -> None:
    assert mean([1.0, 2.0, 3.0]) == 2.0


def test_evaluate_gate_passes_when_both_metrics_clear_threshold() -> None:
    gate = evaluate_gate(
        mean_recall_at_k=0.9,
        mean_faithfulness=4.5,
        recall_threshold=0.85,
        faithfulness_threshold=4.0,
    )

    assert gate.passed is True
    assert gate.reasons == []


def test_evaluate_gate_fails_when_recall_is_below_threshold() -> None:
    gate = evaluate_gate(
        mean_recall_at_k=0.5,
        mean_faithfulness=4.5,
        recall_threshold=0.85,
        faithfulness_threshold=4.0,
    )

    assert gate.passed is False
    assert len(gate.reasons) == 1
    assert "recall@k" in gate.reasons[0]


def test_evaluate_gate_fails_when_faithfulness_is_below_threshold() -> None:
    gate = evaluate_gate(
        mean_recall_at_k=0.9,
        mean_faithfulness=3.0,
        recall_threshold=0.85,
        faithfulness_threshold=4.0,
    )

    assert gate.passed is False
    assert len(gate.reasons) == 1
    assert "faithfulness" in gate.reasons[0]


def test_evaluate_gate_reports_both_reasons_when_both_metrics_fail() -> None:
    gate = evaluate_gate(
        mean_recall_at_k=0.1,
        mean_faithfulness=1.0,
        recall_threshold=0.85,
        faithfulness_threshold=4.0,
    )

    assert gate.passed is False
    assert len(gate.reasons) == 2
