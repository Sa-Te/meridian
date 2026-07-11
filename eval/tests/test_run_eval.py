import asyncio
from typing import Any

import pytest

from eval.run_eval import _RETRY_ATTEMPTS, _aggregate, _with_retry


def _make_result(
    *,
    question_id: str,
    category: str,
    recall_at_k: float | None,
    precision_at_k: float | None,
    faithfulness: int,
    relevance: int,
    answered_as_expected: bool,
) -> dict[str, Any]:
    return {
        "id": question_id,
        "category": category,
        "recall_at_k": recall_at_k,
        "precision_at_k": precision_at_k,
        "faithfulness": faithfulness,
        "relevance": relevance,
        "answered_as_expected": answered_as_expected,
    }


class _FlakyThenSucceeds:
    def __init__(self, failures_before_success: int) -> None:
        self._failures_before_success = failures_before_success
        self.call_count = 0

    async def __call__(self) -> str:
        self.call_count += 1
        if self.call_count <= self._failures_before_success:
            raise RuntimeError(f"transient failure #{self.call_count}")
        return "ok"


async def _run_with_no_sleep(
    monkeypatch: pytest.MonkeyPatch, call: object, **kwargs: object
) -> str:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("eval.run_eval.asyncio.sleep", _no_sleep)
    return await _with_retry(call, **kwargs)  # type: ignore[arg-type]


def test_with_retry_returns_immediately_on_first_success(monkeypatch: pytest.MonkeyPatch) -> None:
    flaky = _FlakyThenSucceeds(failures_before_success=0)

    result = asyncio.run(_run_with_no_sleep(monkeypatch, flaky, label="test"))

    assert result == "ok"
    assert flaky.call_count == 1


def test_with_retry_retries_on_transient_failure_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flaky = _FlakyThenSucceeds(failures_before_success=2)

    result = asyncio.run(_run_with_no_sleep(monkeypatch, flaky, label="test"))

    assert result == "ok"
    assert flaky.call_count == 3


def test_with_retry_raises_the_last_error_after_exhausting_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flaky = _FlakyThenSucceeds(failures_before_success=99)

    with pytest.raises(RuntimeError, match=f"transient failure #{_RETRY_ATTEMPTS}"):
        asyncio.run(_run_with_no_sleep(monkeypatch, flaky, label="test"))

    assert flaky.call_count == _RETRY_ATTEMPTS


def test_aggregate_computes_overall_and_per_category_means() -> None:
    results = [
        _make_result(
            question_id="df-1",
            category="direct_fact",
            recall_at_k=1.0,
            precision_at_k=0.125,
            faithfulness=5,
            relevance=5,
            answered_as_expected=True,
        ),
        _make_result(
            question_id="df-2",
            category="direct_fact",
            recall_at_k=0.0,
            precision_at_k=0.0,
            faithfulness=3,
            relevance=3,
            answered_as_expected=False,
        ),
        _make_result(
            question_id="oos-1",
            category="out_of_scope",
            recall_at_k=None,
            precision_at_k=None,
            faithfulness=5,
            relevance=5,
            answered_as_expected=True,
        ),
    ]

    aggregate = _aggregate(results)

    assert aggregate["question_count"] == 3
    # Only the two in-scope (non out-of-scope) questions count toward recall/precision.
    assert aggregate["mean_recall_at_k"] == 0.5
    assert aggregate["mean_precision_at_k"] == pytest.approx(0.0625)
    # Faithfulness/relevance are judged for every question, including declines.
    assert aggregate["mean_faithfulness"] == pytest.approx((5 + 3 + 5) / 3)
    assert aggregate["answered_as_expected_rate"] == pytest.approx(2 / 3)

    direct_fact = aggregate["by_category"]["direct_fact"]
    assert direct_fact["count"] == 2
    assert direct_fact["mean_recall_at_k"] == 0.5

    out_of_scope = aggregate["by_category"]["out_of_scope"]
    assert out_of_scope["count"] == 1
    # An out-of-scope question has no recall@k to score; mean() of an empty
    # set of scored rows is 0.0 by convention, not a crash.
    assert out_of_scope["mean_recall_at_k"] == 0.0
    assert out_of_scope["answered_as_expected_rate"] == 1.0
