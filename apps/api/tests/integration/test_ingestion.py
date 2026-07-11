"""Integration tests for the parse -> chunk -> embed -> store pipeline and
the POST /meetings/ingest endpoint that wraps it. Requires a real Postgres
database migrated to head. Uses FakeEmbeddingProvider (see tests/fakes.py)
rather than a real model/API -- embedding quality itself is covered
separately by tests/integration/test_local_bge_embedding_provider.py.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db import async_session_factory, engine
from app.dependencies import get_cached_embedding_provider
from app.main import app
from app.models.orm import Meeting
from app.repositories.meeting_repository import MeetingRepository
from app.services.ingestion import ingest_transcript
from tests.fakes import FakeEmbeddingProvider

_SAMPLE_TRANSCRIPT = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "transcripts"
    / "2026-02-19_leadership-sync-roadmap-prioritization.txt"
)


@pytest.fixture(autouse=True)
async def _clean_meetings_table() -> None:
    yield
    async with engine.begin() as connection:
        await connection.execute(delete(Meeting))


async def test_ingest_transcript_stores_meeting_and_chunks_with_embeddings() -> None:
    raw_text = _SAMPLE_TRANSCRIPT.read_text()
    fake_provider = FakeEmbeddingProvider()

    async with async_session_factory() as session:
        meeting = await ingest_transcript(
            filename=_SAMPLE_TRANSCRIPT.name,
            raw_text=raw_text,
            embedding_provider=fake_provider,
            session=session,
        )

    assert meeting.title == "Leadership Sync Roadmap Prioritization"
    assert meeting.participants == ["Dhruvisha", "Todd"]
    assert len(meeting.chunks) == 16
    assert [chunk.chunk_index for chunk in meeting.chunks] == list(range(16))
    assert all(chunk.embedding is not None for chunk in meeting.chunks)
    assert len(fake_provider.calls) == 1
    assert len(fake_provider.calls[0]) == 16

    async with async_session_factory() as session:
        fetched = await MeetingRepository(session).get_by_id(meeting.id)

    assert fetched is not None
    assert len(fetched.chunks) == 16


async def test_ingest_transcript_rejects_a_filename_with_no_date_prefix() -> None:
    async with async_session_factory() as session:
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            await ingest_transcript(
                filename="not-a-dated-filename.txt",
                raw_text="[00:00:00] Alice: Hi.\n",
                embedding_provider=FakeEmbeddingProvider(),
                session=session,
            )


async def test_ingest_endpoint_returns_meeting_id_and_chunk_count() -> None:
    app.dependency_overrides[get_cached_embedding_provider] = FakeEmbeddingProvider
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with _SAMPLE_TRANSCRIPT.open("rb") as file_handle:
                response = await client.post(
                    "/meetings/ingest",
                    files={"file": (_SAMPLE_TRANSCRIPT.name, file_handle, "text/plain")},
                )
    finally:
        app.dependency_overrides.pop(get_cached_embedding_provider, None)

    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] == 16

    async with async_session_factory() as session:
        fetched = await MeetingRepository(session).get_by_id(body["meeting_id"])
    assert fetched is not None


async def test_ingest_endpoint_rejects_unparseable_filename() -> None:
    app.dependency_overrides[get_cached_embedding_provider] = FakeEmbeddingProvider
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/meetings/ingest",
                files={
                    "file": ("not-a-dated-filename.txt", b"[00:00:00] Alice: Hi.\n", "text/plain")
                },
            )
    finally:
        app.dependency_overrides.pop(get_cached_embedding_provider, None)

    assert response.status_code == 422
