"""Integration test: requires a real Postgres database migrated to head
(alembic upgrade head) and reachable via DATABASE_URL. See ROADMAP.md Phase 1.
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.db import async_session_factory, engine
from app.models.orm import Meeting
from app.repositories.meeting_repository import MeetingRepository
from app.services.transcript_loader import load_meeting_from_file

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


async def test_sample_transcript_round_trips_through_the_loader() -> None:
    meeting = load_meeting_from_file(_SAMPLE_TRANSCRIPT)

    async with async_session_factory() as session:
        saved = await MeetingRepository(session).create(meeting)

    assert saved.title == "Leadership Sync Roadmap Prioritization"
    assert saved.date.isoformat() == "2026-02-19"
    assert saved.participants == ["Dhruvisha", "Todd"]
    assert saved.source_filename == _SAMPLE_TRANSCRIPT.name
    assert saved.raw_text == _SAMPLE_TRANSCRIPT.read_text()

    assert len(saved.chunks) == 16
    assert [chunk.chunk_index for chunk in saved.chunks] == list(range(16))
    assert saved.chunks[0].speaker == "Todd"
    assert saved.chunks[0].start_ts == 4
    assert saved.chunks[0].embedding is None

    async with async_session_factory() as session:
        fetched = await MeetingRepository(session).get_by_id(saved.id)

    assert fetched is not None
    assert fetched.id == saved.id
    assert len(fetched.chunks) == 16
    assert [chunk.text for chunk in fetched.chunks] == [chunk.text for chunk in saved.chunks]


async def test_missing_meeting_returns_none() -> None:
    async with async_session_factory() as session:
        fetched = await MeetingRepository(session).get_by_id(uuid.uuid4())

    assert fetched is None
