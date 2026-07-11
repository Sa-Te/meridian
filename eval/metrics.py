"""Pure scoring functions for the eval harness: retrieval precision@k/
recall@k and report aggregation. See docs/adr/0009. Kept free of any
DB/LLM/network dependency so these are testable with plain data.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from uuid import UUID


def precision_at_k(retrieved_ids: Sequence[UUID], expected_ids: set[UUID]) -> float:
    """Fraction of the retrieved set that is actually relevant.

    0.0 when nothing was retrieved. expected_ids may be empty (an
    out-of-scope question, with no correct chunk at all) -- callers should
    not call this for out-of-scope questions; precision/recall aren't
    meaningful against an empty ground truth, and this returns 0.0 rather
    than dividing by zero if they do.
    """
    if not retrieved_ids:
        return 0.0
    relevant_retrieved = len(set(retrieved_ids) & expected_ids)
    return relevant_retrieved / len(retrieved_ids)


def recall_at_k(retrieved_ids: Sequence[UUID], expected_ids: set[UUID]) -> float:
    """1.0 if at least one of the expected chunk ids was retrieved, 0.0
    otherwise (including when expected_ids is empty -- see precision_at_k's
    note; callers should not call this for out-of-scope questions).

    This is hit-rate, not fractional multi-document recall. A golden
    question's expected_ids can contain more than one chunk id when the
    transcript states the same fact in more than one place (an initial
    proposal and a later recap, say) -- each such chunk is an independently
    sufficient, equally correct citation for that one fact, not a separate
    fact that also needs finding. Scoring fractionally would penalize the
    retriever for not returning literally every restatement of a single
    fact, which isn't a retrieval quality problem. See docs/adr/0009.
    """
    if not expected_ids:
        return 0.0
    return 1.0 if set(retrieved_ids) & expected_ids else 0.0


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


@dataclass(frozen=True)
class GateResult:
    """Whether the eval run clears the CI quality gate, and why."""

    passed: bool
    reasons: list[str]


def evaluate_gate(
    *,
    mean_recall_at_k: float,
    mean_faithfulness: float,
    recall_threshold: float,
    faithfulness_threshold: float,
) -> GateResult:
    """The CI-blocking gate: mean retrieval recall@k and mean LLM-judge
    faithfulness must both clear their threshold. See docs/adr/0009 for why
    these two (and not relevance or guardrail accuracy, which are reported
    but not gated on) were chosen as the hard gate, and for the specific
    threshold values.
    """
    reasons = []
    if mean_recall_at_k < recall_threshold:
        reasons.append(
            f"mean recall@k {mean_recall_at_k:.3f} is below threshold {recall_threshold:.3f}"
        )
    if mean_faithfulness < faithfulness_threshold:
        reasons.append(
            f"mean faithfulness {mean_faithfulness:.3f} is below threshold "
            f"{faithfulness_threshold:.3f}"
        )
    return GateResult(passed=not reasons, reasons=reasons)
