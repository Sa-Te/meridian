"""Evaluation harness: retrieval quality + LLM-as-judge answer quality
against eval/golden_dataset/golden_questions.json, wired in as a CI gate.
See docs/adr/0009 and ROADMAP.md Phase 5.

Ingests every transcript under data/transcripts/ (reusing an already-
ingested Meeting by source_filename if one exists, so repeated local runs
don't pile up duplicates -- see MeetingRepository.get_by_source_filename),
then for each golden question:

1. Runs the real hybrid_search retrieval and scores precision@k/recall@k
   against the question's expected supporting chunk(s).
2. Runs the real ask flow's guardrail + generate_answer over that same
   retrieved set, exactly as app/routers/ask.py does.
3. Sends the question, the retrieved excerpts, and the generated answer to
   a separate, clearly-labelled LLM-judge call (eval/judge.py) scoring
   faithfulness and relevance from 1-5.

Aggregates the results, writes the full report to eval/results/latest.json,
prints a human-readable summary, and exits non-zero if mean recall@k or
mean faithfulness falls below its threshold -- the actual CI quality gate.

Usage (from the repo root, with the apps/api virtualenv active and
DATABASE_URL pointing at a migrated database):

    python -m eval.run_eval
"""

import asyncio
import json
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import async_session_factory
from app.models.orm import Meeting
from app.providers.embedding.base import EmbeddingProvider
from app.providers.embedding.factory import get_embedding_provider
from app.providers.llm.base import LLMProvider
from app.providers.llm.factory import get_llm_provider
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.meeting_repository import MeetingRepository
from app.services.answer_generation import UNSUPPORTED_ANSWER, generate_answer
from app.services.guardrails.output_guardrail import passes_retrieval_confidence
from app.services.ingestion import ingest_transcript
from app.services.retrieval import RetrievedChunk, hybrid_search
from eval.golden import GoldenQuestion, load_golden_questions, resolve_expected_chunk_ids
from eval.judge import judge_answer
from eval.metrics import evaluate_gate, mean, precision_at_k, recall_at_k

DATA_TRANSCRIPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "transcripts"
RESULTS_PATH = Path(__file__).resolve().parent / "results" / "latest.json"

# See docs/adr/0009 for the justification behind these two specific values.
# These are the only two metrics ROADMAP.md Phase 5 names as CI-gating;
# relevance and guardrail-decline accuracy are reported but not gated on.
RECALL_AT_K_THRESHOLD = 0.85
FAITHFULNESS_THRESHOLD = 4.0

_RETRY_ATTEMPTS = 4
_RETRY_BASE_DELAY_SECONDS = 10.0

# Free-tier Gemini keys cap generate_content at 15 requests/minute (see
# ADR-0013's free-tier trade-off). This eval script makes two real LLM calls
# per in-scope question (generate + judge) back-to-back, unlike normal
# request traffic, so it paces those calls itself rather than relying solely
# on reactive retry-after-429 -- 4.5s of spacing keeps steady-state throughput
# under the 15 RPM cap with headroom, rather than bursting into it every time.
_MIN_LLM_CALL_INTERVAL_SECONDS = 4.5


class _LLMRateLimiter:
    """Enforces a minimum interval between successive real LLM calls."""

    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval_seconds = min_interval_seconds
        self._last_call_at: float | None = None

    async def wait(self) -> None:
        if self._last_call_at is not None:
            remaining = self._min_interval_seconds - (time.monotonic() - self._last_call_at)
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_call_at = time.monotonic()


_llm_rate_limiter = _LLMRateLimiter(_MIN_LLM_CALL_INTERVAL_SECONDS)


async def _with_retry[T](call: Callable[[], Awaitable[T]], *, label: str) -> T:
    """Retries a real external API call (embedding/LLM) with exponential
    backoff -- a backstop for the rare 429/5xx that pacing alone (see
    _LLMRateLimiter) doesn't prevent, or a genuine transient vendor error.
    """
    last_error: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return await call()
        except Exception as error:  # noqa: BLE001 -- deliberately broad: any
            # transient failure from a real vendor API should be retried,
            # not just a known subset of exception types.
            last_error = error
            if attempt < _RETRY_ATTEMPTS - 1:
                delay = _RETRY_BASE_DELAY_SECONDS * (2**attempt)
                print(f"  [retry] {label} failed ({error!r}), retrying in {delay:.0f}s...")
                await asyncio.sleep(delay)
    assert last_error is not None
    raise last_error


async def _load_meetings(
    *, session: AsyncSession, embedding_provider: EmbeddingProvider
) -> dict[str, Meeting]:
    """Ensures every transcript under data/transcripts/ is ingested, reusing
    an existing Meeting by source_filename rather than re-ingesting one that
    a prior local run already created.
    """
    meeting_repository = MeetingRepository(session)
    meetings_by_filename: dict[str, Meeting] = {}
    for path in sorted(DATA_TRANSCRIPTS_DIR.glob("*.txt")):
        existing = await meeting_repository.get_by_source_filename(path.name)
        if existing is not None:
            meetings_by_filename[path.name] = existing
            continue
        print(f"Ingesting {path.name}...")
        meeting = await ingest_transcript(
            filename=path.name,
            raw_text=path.read_text(),
            embedding_provider=embedding_provider,
            session=session,
        )
        meetings_by_filename[path.name] = meeting
    return meetings_by_filename


async def _score_question(
    question: GoldenQuestion,
    *,
    meetings_by_filename: dict[str, Meeting],
    session: AsyncSession,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    settings: Settings,
) -> dict[str, Any]:
    expected_chunk_ids: set[UUID] = set()
    if question.source_meeting_filename is not None:
        meeting = meetings_by_filename[question.source_meeting_filename]
        expected_chunk_ids = resolve_expected_chunk_ids(question, meeting.chunks)

    query_embedding = await _with_retry(
        lambda: embedding_provider.embed([question.question]), label=f"{question.id} embed"
    )
    retrieved: list[RetrievedChunk] = await hybrid_search(
        query_text=question.question,
        query_embedding=query_embedding[0],
        chunk_repository=ChunkRepository(session),
        meeting_id=None,
        top_k=settings.retrieval_top_k,
        candidate_pool_size=settings.retrieval_candidate_pool_size,
        vector_weight=settings.retrieval_vector_weight,
        text_weight=settings.retrieval_text_weight,
    )
    retrieved_ids = [r.chunk.id for r in retrieved]

    is_out_of_scope = question.category == "out_of_scope"
    precision = None if is_out_of_scope else precision_at_k(retrieved_ids, expected_chunk_ids)
    recall = None if is_out_of_scope else recall_at_k(retrieved_ids, expected_chunk_ids)

    confidence_threshold = settings.retrieval_confidence_threshold
    if not passes_retrieval_confidence(retrieved, threshold=confidence_threshold):
        answer, supported, cited_ids = UNSUPPORTED_ANSWER, False, set[UUID]()
    else:
        await _llm_rate_limiter.wait()
        result = await _with_retry(
            lambda: generate_answer(
                question=question.question,
                retrieved_chunks=[r.chunk for r in retrieved],
                llm_provider=llm_provider,
            ),
            label=f"{question.id} generate",
        )
        answer = result.answer
        supported = result.supported
        cited_ids = {citation.chunk_id for citation in result.citations}

    await _llm_rate_limiter.wait()
    verdict = await _with_retry(
        lambda: judge_answer(
            question=question.question,
            answer=answer,
            retrieved_chunks=[r.chunk for r in retrieved],
            cited_chunk_ids=cited_ids,
            llm_provider=llm_provider,
        ),
        label=f"{question.id} judge",
    )

    expected_supported = not is_out_of_scope
    return {
        "id": question.id,
        "category": question.category,
        "question": question.question,
        "expected_answer": question.expected_answer,
        "source_meeting_filename": question.source_meeting_filename,
        "expected_chunk_ids": sorted(str(i) for i in expected_chunk_ids),
        "retrieved_chunk_ids": [str(i) for i in retrieved_ids],
        "precision_at_k": precision,
        "recall_at_k": recall,
        "supported": supported,
        "expected_supported": expected_supported,
        "answered_as_expected": supported == expected_supported,
        "answer": answer,
        "cited_chunk_ids": sorted(str(i) for i in cited_ids),
        "faithfulness": verdict.faithfulness,
        "faithfulness_reasoning": verdict.faithfulness_reasoning,
        "relevance": verdict.relevance,
        "relevance_reasoning": verdict.relevance_reasoning,
    }


def _aggregate(question_results: list[dict[str, Any]]) -> dict[str, Any]:
    in_scope = [r for r in question_results if r["category"] != "out_of_scope"]
    categories = sorted({r["category"] for r in question_results})

    by_category = {}
    for category in categories:
        rows = [r for r in question_results if r["category"] == category]
        scored_rows = [r for r in rows if r["recall_at_k"] is not None]
        by_category[category] = {
            "count": len(rows),
            "mean_precision_at_k": mean(r["precision_at_k"] for r in scored_rows),
            "mean_recall_at_k": mean(r["recall_at_k"] for r in scored_rows),
            "mean_faithfulness": mean(r["faithfulness"] for r in rows),
            "mean_relevance": mean(r["relevance"] for r in rows),
            "answered_as_expected_rate": mean(
                1.0 if r["answered_as_expected"] else 0.0 for r in rows
            ),
        }

    return {
        "question_count": len(question_results),
        "mean_precision_at_k": mean(r["precision_at_k"] for r in in_scope),
        "mean_recall_at_k": mean(r["recall_at_k"] for r in in_scope),
        "mean_faithfulness": mean(r["faithfulness"] for r in question_results),
        "mean_relevance": mean(r["relevance"] for r in question_results),
        "answered_as_expected_rate": mean(
            1.0 if r["answered_as_expected"] else 0.0 for r in question_results
        ),
        "by_category": by_category,
    }


def _print_report(report: dict[str, Any]) -> None:
    aggregate = report["aggregate"]
    print("\n=== Meridian eval report ===")
    print(f"Questions scored: {aggregate['question_count']}")
    print(f"Mean precision@k (in-scope): {aggregate['mean_precision_at_k']:.3f}")
    print(f"Mean recall@k (in-scope):    {aggregate['mean_recall_at_k']:.3f}")
    print(f"Mean faithfulness (1-5):     {aggregate['mean_faithfulness']:.3f}")
    print(f"Mean relevance (1-5):        {aggregate['mean_relevance']:.3f}")
    print(f"Answered-as-expected rate:   {aggregate['answered_as_expected_rate']:.3f}")
    print("\nBy category:")
    for category, stats in aggregate["by_category"].items():
        print(
            f"  {category:15s} n={stats['count']:2d}  "
            f"recall@k={stats['mean_recall_at_k']:.3f}  "
            f"faithfulness={stats['mean_faithfulness']:.2f}  "
            f"relevance={stats['mean_relevance']:.2f}  "
            f"answered_as_expected={stats['answered_as_expected_rate']:.2f}"
        )

    gate = report["gate"]
    print(f"\nGate: {'PASSED' if gate['passed'] else 'FAILED'}")
    for reason in gate["reasons"]:
        print(f"  - {reason}")
    print()


async def run() -> dict[str, Any]:
    settings = get_settings()
    if settings.llm_provider.lower() != "gemini":
        raise SystemExit(
            "Eval requires LLM_PROVIDER=gemini: the LLM-judge uses "
            "generate_structured, which AnthropicLLMProvider does not yet "
            "implement (see docs/adr/0008). Current LLM_PROVIDER="
            f"{settings.llm_provider!r}."
        )

    embedding_provider = get_embedding_provider(settings)
    llm_provider = get_llm_provider(settings)
    golden_questions = load_golden_questions()

    async with async_session_factory() as session:
        meetings_by_filename = await _load_meetings(
            session=session, embedding_provider=embedding_provider
        )

        question_results = []
        for question in golden_questions:
            print(f"Scoring {question.id}: {question.question}")
            result = await _score_question(
                question,
                meetings_by_filename=meetings_by_filename,
                session=session,
                embedding_provider=embedding_provider,
                llm_provider=llm_provider,
                settings=settings,
            )
            question_results.append(result)

    aggregate = _aggregate(question_results)
    gate = evaluate_gate(
        mean_recall_at_k=aggregate["mean_recall_at_k"],
        mean_faithfulness=aggregate["mean_faithfulness"],
        recall_threshold=RECALL_AT_K_THRESHOLD,
        faithfulness_threshold=FAITHFULNESS_THRESHOLD,
    )

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "thresholds": {
            "recall_at_k": RECALL_AT_K_THRESHOLD,
            "faithfulness": FAITHFULNESS_THRESHOLD,
        },
        "gate": {"passed": gate.passed, "reasons": gate.reasons},
        "aggregate": aggregate,
        "questions": question_results,
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    report = asyncio.run(run())
    _print_report(report)
    sys.exit(0 if report["gate"]["passed"] else 1)


if __name__ == "__main__":
    main()
