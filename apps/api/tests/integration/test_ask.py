"""Integration tests for POST /meetings/{id}/ask and POST /ask. Requires a
real Postgres database migrated to head. Uses FakeEmbeddingProvider and
FakeLLMProvider (see tests/fakes.py) rather than real models/APIs --
generation quality itself isn't what these tests are exercising; the
hybrid-search-to-cited-answer plumbing is.
"""

import json
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db import async_session_factory, engine
from app.dependencies import get_cached_embedding_provider, get_cached_llm_provider
from app.main import app
from app.models.orm import Meeting
from app.services.ingestion import ingest_transcript
from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider

_ALERT_THRESHOLDS_TRANSCRIPT = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "transcripts"
    / "2026-01-29_clinical-advisory-alert-thresholds.txt"
)


@pytest.fixture(autouse=True)
async def _clean_meetings_table() -> None:
    yield
    async with engine.begin() as connection:
        await connection.execute(delete(Meeting))


def _override_providers(llm: FakeLLMProvider) -> None:
    app.dependency_overrides[get_cached_embedding_provider] = FakeEmbeddingProvider
    app.dependency_overrides[get_cached_llm_provider] = lambda: llm


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_cached_embedding_provider, None)
    app.dependency_overrides.pop(get_cached_llm_provider, None)


async def test_ask_meeting_with_known_answer_returns_correct_citation() -> None:
    async with async_session_factory() as session:
        meeting = await ingest_transcript(
            filename=_ALERT_THRESHOLDS_TRANSCRIPT.name,
            raw_text=_ALERT_THRESHOLDS_TRANSCRIPT.read_text(),
            embedding_provider=FakeEmbeddingProvider(),
            session=session,
        )

    target_chunk = next(chunk for chunk in meeting.chunks if "five to seven" in chunk.text)

    # FakeEmbeddingProvider carries no real semantic signal, so this test
    # exercises the full-text side of hybrid search -- the question is
    # worded to share exact (stemmed) vocabulary with target_chunk, since
    # plainto_tsquery ANDs every term together.
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
            response = await client.post(
                f"/meetings/{meeting.id}/ask",
                json={
                    "question": (
                        "Logged workouts with heart rate data before we trust a "
                        "personal baseline?"
                    )
                },
            )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is True
    assert "five to seven" in body["answer"]
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["chunk_id"] == str(target_chunk.id)
    assert citation["meeting_id"] == str(meeting.id)
    assert citation["start_ts"] == target_chunk.start_ts
    assert len(fake_llm.calls) == 1


async def test_ask_global_with_out_of_scope_question_returns_not_well_supported() -> None:
    async with async_session_factory() as session:
        await ingest_transcript(
            filename=_ALERT_THRESHOLDS_TRANSCRIPT.name,
            raw_text=_ALERT_THRESHOLDS_TRANSCRIPT.read_text(),
            embedding_provider=FakeEmbeddingProvider(),
            session=session,
        )

    honest_refusal = json.dumps(
        {
            "supported": False,
            "answer": "The transcripts do not discuss this topic.",
            "citations": [],
        }
    )
    fake_llm = FakeLLMProvider(responses=[honest_refusal])
    _override_providers(fake_llm)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/ask", json={"question": "What is the capital of France?"}
            )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is False
    assert body["citations"] == []
    assert body["answer"] == "The transcripts do not discuss this topic."


async def test_ask_global_with_empty_corpus_returns_unsupported_without_calling_the_llm() -> None:
    fake_llm = FakeLLMProvider(responses=[])
    _override_providers(fake_llm)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/ask", json={"question": "Anything at all?"})
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is False
    assert body["citations"] == []
    assert fake_llm.calls == []


async def test_ask_meeting_not_found_returns_404() -> None:
    fake_llm = FakeLLMProvider(responses=[])
    _override_providers(fake_llm)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/meetings/{uuid.uuid4()}/ask", json={"question": "Anything?"}
            )
    finally:
        _clear_overrides()

    assert response.status_code == 404
