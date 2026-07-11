"""Integration tests for GET /meetings/{id}/decisions,
GET /meetings/{id}/action-items, and the global GET /action-items with
status/owner filtering. Requires a real Postgres database migrated to head.
Seeds Decision/ActionItem rows directly rather than through extraction --
extraction correctness is covered separately by
tests/integration/test_extraction.py.
"""

import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db import async_session_factory, engine
from app.main import app
from app.models.orm import ActionItem, ActionItemStatus, Chunk, Decision, Meeting


@pytest.fixture(autouse=True)
async def _clean_meetings_table() -> None:
    yield
    async with engine.begin() as connection:
        await connection.execute(delete(Meeting))


async def _seed_meeting_with_extractions() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    meeting = Meeting(
        title="Test Meeting",
        date=date(2026, 1, 1),
        participants=["Dr. Vasquez", "Naomi"],
        source_filename="t.txt",
        raw_text="hello",
        chunks=[Chunk(speaker="Dr. Vasquez", start_ts=0, end_ts=10, text="hello", chunk_index=0)],
    )

    async with async_session_factory() as session:
        session.add(meeting)
        await session.flush()
        chunk_id = meeting.chunks[0].id
        decision = Decision(
            meeting_id=meeting.id,
            text="Ship the new threshold.",
            source_chunk_id=chunk_id,
            confidence=0.9,
        )
        action_item = ActionItem(
            meeting_id=meeting.id,
            text="Send the source.",
            owner="Dr. Vasquez",
            source_chunk_id=chunk_id,
            confidence=0.9,
            status=ActionItemStatus.OPEN,
        )
        session.add_all([decision, action_item])
        await session.flush()
        # Capture ids into plain variables before commit expires the ORM
        # objects' attributes -- accessing them afterward would trigger a
        # synchronous lazy-refresh that isn't safe from an async context.
        ids = (meeting.id, decision.id, action_item.id)
        await session.commit()
        return ids


async def test_get_meeting_decisions_returns_seeded_decision() -> None:
    meeting_id, decision_id, _ = await _seed_meeting_with_extractions()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/meetings/{meeting_id}/decisions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(decision_id)
    assert body[0]["text"] == "Ship the new threshold."


async def test_get_meeting_action_items_returns_seeded_action_item() -> None:
    meeting_id, _, action_item_id = await _seed_meeting_with_extractions()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/meetings/{meeting_id}/action-items")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(action_item_id)
    assert body[0]["owner"] == "Dr. Vasquez"
    assert body[0]["status"] == "open"


async def test_get_meeting_decisions_404s_for_unknown_meeting() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/meetings/{uuid.uuid4()}/decisions")

    assert response.status_code == 404


async def test_global_action_items_filters_by_status_and_owner() -> None:
    _, _, open_item_id = await _seed_meeting_with_extractions()

    meeting = Meeting(
        title="Second Meeting",
        date=date(2026, 1, 2),
        participants=["Naomi"],
        source_filename="t2.txt",
        raw_text="hello again",
        chunks=[Chunk(speaker="Naomi", start_ts=0, end_ts=10, text="hello again", chunk_index=0)],
    )
    async with async_session_factory() as session:
        session.add(meeting)
        await session.flush()
        done_item = ActionItem(
            meeting_id=meeting.id,
            text="Already finished task.",
            owner="Naomi",
            source_chunk_id=meeting.chunks[0].id,
            confidence=0.9,
            status=ActionItemStatus.DONE,
        )
        session.add(done_item)
        await session.flush()
        done_item_id = done_item.id
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        all_items = await client.get("/action-items")
        open_only = await client.get("/action-items", params={"status": "open"})
        naomi_only = await client.get("/action-items", params={"owner": "Naomi"})

    assert {item["id"] for item in all_items.json()} == {str(open_item_id), str(done_item_id)}
    assert [item["id"] for item in open_only.json()] == [str(open_item_id)]
    assert [item["id"] for item in naomi_only.json()] == [str(done_item_id)]
