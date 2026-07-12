"""Integration tests for DELETE /meetings/{id}. Requires a real Postgres
database migrated to head. Cascade-delete behavior for chunks/decisions/
action items is already covered at the DB/ORM level by
test_domain_schema_constraints.py -- these tests only cover the endpoint's
own contract (status codes, and that the row is actually gone afterward).
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


async def _seed_meeting(
    *, title: str = "A Meeting", meeting_date: date = date(2026, 1, 1)
) -> uuid.UUID:
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


async def test_delete_meeting_removes_it() -> None:
    meeting_id = await _seed_meeting()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        delete_response = await client.delete(f"/meetings/{meeting_id}")
        get_response = await client.get(f"/meetings/{meeting_id}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert get_response.status_code == 404


async def test_delete_meeting_404s_for_unknown_meeting() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(f"/meetings/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_delete_meeting_does_not_affect_other_meetings() -> None:
    deleted_id = await _seed_meeting(title="To Delete")
    kept_id = await _seed_meeting(title="To Keep")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        delete_response = await client.delete(f"/meetings/{deleted_id}")
        list_response = await client.get("/meetings")

    assert delete_response.status_code == 204
    remaining_ids = [item["id"] for item in list_response.json()]
    assert remaining_ids == [str(kept_id)]
