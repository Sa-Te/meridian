"""Integration tests for GET /meetings and GET /meetings/{id} (Phase 7's
meeting picker). Requires a real Postgres database migrated to head.
"""

import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db import async_session_factory, engine
from app.main import app
from app.models.orm import Meeting


@pytest.fixture(autouse=True)
async def _clean_meetings_table() -> None:
    yield
    async with engine.begin() as connection:
        await connection.execute(delete(Meeting))


async def _seed_meeting(*, title: str, meeting_date: date) -> uuid.UUID:
    async with async_session_factory() as session:
        meeting = Meeting(
            title=title,
            date=meeting_date,
            participants=["Dr. Vasquez", "Naomi"],
            source_filename="t.txt",
            raw_text="hello",
        )
        session.add(meeting)
        await session.commit()
        await session.refresh(meeting)
        return meeting.id


async def test_list_meetings_returns_all_meetings_newest_first() -> None:
    first_id = await _seed_meeting(title="Earlier Meeting", meeting_date=date(2026, 1, 1))
    second_id = await _seed_meeting(title="Later Meeting", meeting_date=date(2026, 2, 1))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/meetings")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [str(second_id), str(first_id)]
    assert "raw_text" not in body[0]


async def test_get_meeting_returns_summary_for_known_meeting() -> None:
    meeting_id = await _seed_meeting(title="A Meeting", meeting_date=date(2026, 1, 1))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/meetings/{meeting_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(meeting_id)
    assert body["title"] == "A Meeting"
    assert "raw_text" not in body


async def test_get_meeting_404s_for_unknown_meeting() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/meetings/{uuid.uuid4()}")

    assert response.status_code == 404
