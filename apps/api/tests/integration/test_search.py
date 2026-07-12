"""Integration tests for GET /search. Requires a real Postgres database
migrated to head. Uses FakeEmbeddingProvider (see tests/fakes.py) --
retrieval-ranking quality itself is covered by
tests/unit/test_retrieval.py; this test exercises the search-endpoint-to-
hybrid-search wiring (query params, meeting_id scoping, response shape).
"""

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db import async_session_factory, engine
from app.dependencies import get_cached_embedding_provider
from app.main import app
from app.models.orm import Meeting
from app.services.ingestion import ingest_transcript
from tests.fakes import FakeEmbeddingProvider

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


def _override_embedding_provider() -> None:
    app.dependency_overrides[get_cached_embedding_provider] = FakeEmbeddingProvider


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_cached_embedding_provider, None)


async def test_search_returns_the_full_text_matching_chunk() -> None:
    async with async_session_factory() as session:
        meeting = await ingest_transcript(
            filename=_ALERT_THRESHOLDS_TRANSCRIPT.name,
            raw_text=_ALERT_THRESHOLDS_TRANSCRIPT.read_text(),
            embedding_provider=FakeEmbeddingProvider(),
            session=session,
        )

    target_chunk = next(chunk for chunk in meeting.chunks if "five to seven" in chunk.text)

    # FakeEmbeddingProvider carries no real semantic signal, so this only
    # asserts the full-text-matched chunk is present in the fused results,
    # not that it ranks first -- fusion weights the (noise-only) vector
    # score too, same reasoning as tests/integration/test_ask.py.
    _override_embedding_provider()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/search",
                params={
                    "query": "five to seven logged workouts with heart rate data",
                    "top_k": 5,
                },
            )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert 0 < len(body["results"]) <= 5
    assert all(isinstance(result["fused_score"], float) for result in body["results"])
    matching_result = next(
        result
        for result in body["results"]
        if result["citation"]["chunk_id"] == str(target_chunk.id)
    )
    assert matching_result["citation"]["meeting_id"] == str(meeting.id)
    assert matching_result["citation"]["text"] == target_chunk.text


async def test_search_scoped_to_meeting_id_excludes_other_meetings() -> None:
    async with async_session_factory() as session:
        meeting = await ingest_transcript(
            filename=_ALERT_THRESHOLDS_TRANSCRIPT.name,
            raw_text=_ALERT_THRESHOLDS_TRANSCRIPT.read_text(),
            embedding_provider=FakeEmbeddingProvider(),
            session=session,
        )

    _override_embedding_provider()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            scoped = await client.get(
                "/search",
                params={"query": "workouts", "meeting_id": str(meeting.id)},
            )
            unrelated_meeting_scoped = await client.get(
                "/search",
                params={"query": "workouts", "meeting_id": str(uuid.uuid4())},
            )
    finally:
        _clear_overrides()

    assert scoped.status_code == 200
    assert len(scoped.json()["results"]) > 0
    assert unrelated_meeting_scoped.status_code == 200
    assert unrelated_meeting_scoped.json()["results"] == []


async def test_search_with_empty_corpus_returns_empty_results() -> None:
    _override_embedding_provider()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/search", params={"query": "anything at all"})
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["results"] == []


async def test_search_rejects_empty_query() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/search", params={"query": ""})

    assert response.status_code == 422
