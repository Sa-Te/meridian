"""Integration tests for DB-enforced invariants from docs/adr/0005: the
confidence range check, the per-meeting chunk_index uniqueness, and the
cascade-delete behavior that makes an uncited Decision/ActionItem impossible.
Requires a real Postgres database migrated to head.
"""

from datetime import date

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db import async_session_factory, engine
from app.models.orm import ActionItem, Chunk, Decision, Meeting


@pytest.fixture(autouse=True)
async def _clean_tables() -> None:
    yield
    async with engine.begin() as connection:
        await connection.execute(delete(Meeting))


def _meeting_with_one_chunk() -> Meeting:
    return Meeting(
        title="Test Meeting",
        date=date(2026, 1, 1),
        participants=["Alice"],
        source_filename="t.txt",
        raw_text="hello",
        chunks=[Chunk(speaker="Alice", start_ts=0, end_ts=10, text="hello", chunk_index=0)],
    )


async def test_decision_confidence_out_of_range_is_rejected_by_db() -> None:
    meeting = _meeting_with_one_chunk()

    async with async_session_factory() as session:
        session.add(meeting)
        await session.flush()
        chunk_id = meeting.chunks[0].id

        session.add(
            Decision(meeting_id=meeting.id, text="bad", source_chunk_id=chunk_id, confidence=1.5)
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_duplicate_chunk_index_within_a_meeting_is_rejected_by_db() -> None:
    meeting = Meeting(
        title="Test Meeting",
        date=date(2026, 1, 1),
        participants=["Alice", "Bob"],
        source_filename="t.txt",
        raw_text="hello",
        chunks=[
            Chunk(speaker="Alice", start_ts=0, end_ts=10, text="a", chunk_index=0),
            Chunk(speaker="Bob", start_ts=10, end_ts=20, text="b", chunk_index=0),
        ],
    )

    async with async_session_factory() as session:
        session.add(meeting)
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_deleting_meeting_cascades_to_chunks_decisions_and_action_items() -> None:
    meeting = _meeting_with_one_chunk()

    async with async_session_factory() as session:
        session.add(meeting)
        await session.flush()
        chunk_id = meeting.chunks[0].id
        session.add(
            Decision(meeting_id=meeting.id, text="d", source_chunk_id=chunk_id, confidence=0.9)
        )
        session.add(
            ActionItem(meeting_id=meeting.id, text="a", source_chunk_id=chunk_id, confidence=0.9)
        )
        await session.commit()
        meeting_id = meeting.id

    async with async_session_factory() as session:
        meeting_to_delete = await session.get(Meeting, meeting_id)
        await session.delete(meeting_to_delete)
        await session.commit()

    async with async_session_factory() as session:
        remaining_chunks = await session.execute(
            select(Chunk).where(Chunk.meeting_id == meeting_id)
        )
        remaining_decisions = await session.execute(
            select(Decision).where(Decision.meeting_id == meeting_id)
        )
        remaining_action_items = await session.execute(
            select(ActionItem).where(ActionItem.meeting_id == meeting_id)
        )

    assert remaining_chunks.first() is None
    assert remaining_decisions.first() is None
    assert remaining_action_items.first() is None


async def test_deleting_source_chunk_cascades_to_its_decisions_and_action_items() -> None:
    meeting = _meeting_with_one_chunk()

    async with async_session_factory() as session:
        session.add(meeting)
        await session.flush()
        chunk_id = meeting.chunks[0].id
        session.add(
            Decision(meeting_id=meeting.id, text="d", source_chunk_id=chunk_id, confidence=0.9)
        )
        session.add(
            ActionItem(meeting_id=meeting.id, text="a", source_chunk_id=chunk_id, confidence=0.9)
        )
        await session.commit()

    async with async_session_factory() as session:
        chunk_to_delete = await session.get(Chunk, chunk_id)
        await session.delete(chunk_to_delete)
        await session.commit()

    async with async_session_factory() as session:
        remaining_decisions = await session.execute(
            select(Decision).where(Decision.source_chunk_id == chunk_id)
        )
        remaining_action_items = await session.execute(
            select(ActionItem).where(ActionItem.source_chunk_id == chunk_id)
        )

    assert remaining_decisions.first() is None
    assert remaining_action_items.first() is None
