"""Integration tests for GET /traces and GET /traces/{id}, and for the
tracing instrumentation wired into POST /ask and POST /meetings/ingest
(app/routers/ask.py, app/routers/meetings.py). Requires a real Postgres
database migrated to head. Uses FakeEmbeddingProvider/FakeLLMProvider --
tracing correctness, not generation quality, is what these exercise.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db import async_session_factory, engine
from app.dependencies import get_cached_embedding_provider, get_cached_llm_provider
from app.main import app
from app.models.orm import Meeting, Trace, TraceOutcome
from app.repositories.trace_repository import TraceRepository
from app.services.ingestion import ingest_transcript
from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider

_ALERT_THRESHOLDS_TRANSCRIPT = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "transcripts"
    / "2026-01-29_clinical-advisory-alert-thresholds.txt"
)


@pytest.fixture(autouse=True)
async def _clean_tables() -> None:
    yield
    async with engine.begin() as connection:
        await connection.execute(delete(Meeting))
        await connection.execute(delete(Trace))


def _override_providers(llm: FakeLLMProvider) -> None:
    app.dependency_overrides[get_cached_embedding_provider] = FakeEmbeddingProvider
    app.dependency_overrides[get_cached_llm_provider] = lambda: llm


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_cached_embedding_provider, None)
    app.dependency_overrides.pop(get_cached_llm_provider, None)


async def _seed_trace(
    *,
    endpoint: str = "POST /ask",
    outcome: TraceOutcome = TraceOutcome.ANSWERED,
    created_at: datetime | None = None,
) -> uuid.UUID:
    async with async_session_factory() as session:
        trace = Trace(
            endpoint=endpoint,
            stages=[
                {
                    "name": "embed",
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "duration_ms": 1.0,
                    "metadata": {},
                }
            ],
            total_duration_ms=1.0,
            input_tokens=0,
            output_tokens=0,
            models_used=["fake-model"],
            outcome=outcome,
        )
        if created_at is not None:
            trace.created_at = created_at
        created = await TraceRepository(session).create(trace)
        return created.id


async def test_asking_a_question_produces_a_retrievable_trace_with_expected_stages() -> None:
    async with async_session_factory() as session:
        meeting = await ingest_transcript(
            filename=_ALERT_THRESHOLDS_TRANSCRIPT.name,
            raw_text=_ALERT_THRESHOLDS_TRANSCRIPT.read_text(),
            embedding_provider=FakeEmbeddingProvider(),
            session=session,
        )
    target_chunk = next(chunk for chunk in meeting.chunks if "five to seven" in chunk.text)

    # Worded to share exact vocabulary with target_chunk so the full-text
    # side of hybrid search matches -- see test_ask.py's identical trick --
    # which is what makes the confidence guardrail pass and the flow reach
    # generate_answer instead of declining early.
    llm_response = json.dumps(
        {
            "supported": True,
            "answer": "At least five to seven logged workouts with heart rate data.",
            "citations": [{"chunk_id": str(target_chunk.id)}],
        }
    )
    fake_llm = FakeLLMProvider(responses=[llm_response])
    _override_providers(fake_llm)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            ask_response = await client.post(
                "/ask",
                json={
                    "question": (
                        "Logged workouts with heart rate data before we trust a personal baseline?"
                    )
                },
            )
            assert ask_response.status_code == 200
            assert ask_response.json()["supported"] is True

            list_response = await client.get("/traces", params={"endpoint": "POST /ask"})
    finally:
        _clear_overrides()

    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1
    trace_summary = body["items"][0]
    assert trace_summary["endpoint"] == "POST /ask"
    assert trace_summary["outcome"] == "answered"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        detail_response = await client.get(f"/traces/{trace_summary['id']}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    stage_names = [stage["name"] for stage in detail["stages"]]
    assert stage_names == [
        "embed",
        "hybrid_search",
        "guardrail_confidence_check",
        "llm_generate",
        "generate_answer",
    ]
    assert detail["total_duration_ms"] >= 0.0
    assert detail["models_used"] == ["fake-model"]


async def test_ingesting_a_transcript_produces_a_retrievable_trace_with_expected_stages() -> None:
    from app.services.extraction import _LLMExtractionPayload

    llm = FakeLLMProvider(
        structured_responses=[_LLMExtractionPayload(decisions=[], action_items=[])]
    )
    _override_providers(llm)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with _ALERT_THRESHOLDS_TRANSCRIPT.open("rb") as file_handle:
                ingest_response = await client.post(
                    "/meetings/ingest",
                    files={"file": (_ALERT_THRESHOLDS_TRANSCRIPT.name, file_handle, "text/plain")},
                )
            assert ingest_response.status_code == 200

            list_response = await client.get(
                "/traces", params={"endpoint": "POST /meetings/ingest"}
            )
    finally:
        _clear_overrides()

    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1
    trace_id = body["items"][0]["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        detail_response = await client.get(f"/traces/{trace_id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    stage_names = [stage["name"] for stage in detail["stages"]]
    assert stage_names == [
        "embed",
        "ingest_transcript",
        "prompt_injection_scan",
        "llm_generate_structured",
        "extract_records",
        "persist_extractions",
    ]
    assert detail["outcome"] == "answered"


async def test_list_traces_filters_by_endpoint() -> None:
    await _seed_trace(endpoint="POST /ask")
    await _seed_trace(endpoint="POST /meetings/ingest")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/traces", params={"endpoint": "POST /ask"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["endpoint"] == "POST /ask"


async def test_list_traces_filters_by_outcome() -> None:
    await _seed_trace(outcome=TraceOutcome.ANSWERED)
    await _seed_trace(outcome=TraceOutcome.DECLINED)
    await _seed_trace(outcome=TraceOutcome.ERROR)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/traces", params={"outcome": "declined"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["outcome"] == "declined"


async def test_list_traces_filters_by_date() -> None:
    await _seed_trace(created_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    await _seed_trace(created_at=datetime(2026, 6, 15, 12, 0, tzinfo=UTC))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/traces", params={"date": "2026-01-01"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1


async def test_list_traces_paginates_with_limit_and_offset() -> None:
    for _ in range(5):
        await _seed_trace()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_page = await client.get("/traces", params={"limit": 2, "offset": 0})
        second_page = await client.get("/traces", params={"limit": 2, "offset": 2})

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.json()["total"] == 5
    assert second_page.json()["total"] == 5
    assert len(first_page.json()["items"]) == 2
    assert len(second_page.json()["items"]) == 2
    first_ids = {item["id"] for item in first_page.json()["items"]}
    second_ids = {item["id"] for item in second_page.json()["items"]}
    assert first_ids.isdisjoint(second_ids)


async def test_get_trace_returns_full_detail() -> None:
    trace_id = await _seed_trace()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/traces/{trace_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(trace_id)
    assert len(body["stages"]) == 1
    assert body["stages"][0]["name"] == "embed"


async def test_get_trace_returns_404_for_unknown_id() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/traces/{uuid.uuid4()}")

    assert response.status_code == 404
