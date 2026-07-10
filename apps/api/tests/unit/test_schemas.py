import uuid
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.models.orm import ActionItemStatus, Meeting
from app.models.schemas import (
    ActionItemCreate,
    ChunkCreate,
    DecisionCreate,
    MeetingRead,
)


def test_meeting_read_builds_from_orm_object_not_a_dict() -> None:
    orm_meeting = Meeting(
        id=uuid.uuid4(),
        title="Sprint Review",
        date=date(2026, 1, 1),
        participants=["Alice", "Bob"],
        source_filename="a.txt",
        raw_text="raw text",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    schema = MeetingRead.model_validate(orm_meeting)

    assert schema.title == "Sprint Review"
    assert schema.participants == ["Alice", "Bob"]
    assert schema.raw_text == "raw text"


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_decision_create_rejects_confidence_out_of_bounds(confidence: float) -> None:
    with pytest.raises(ValidationError):
        DecisionCreate(text="We decided X", source_chunk_id=uuid.uuid4(), confidence=confidence)


@pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
def test_decision_create_accepts_boundary_confidence(confidence: float) -> None:
    decision = DecisionCreate(
        text="We decided X", source_chunk_id=uuid.uuid4(), confidence=confidence
    )

    assert decision.confidence == confidence


def test_action_item_create_defaults_status_to_open_with_no_owner_or_due_date() -> None:
    item = ActionItemCreate(text="Do the thing", source_chunk_id=uuid.uuid4(), confidence=0.8)

    assert item.status == ActionItemStatus.OPEN
    assert item.owner is None
    assert item.due_date is None


def test_action_item_create_rejects_confidence_out_of_bounds() -> None:
    with pytest.raises(ValidationError):
        ActionItemCreate(text="x", source_chunk_id=uuid.uuid4(), confidence=1.5)


def test_chunk_create_rejects_negative_timestamps() -> None:
    with pytest.raises(ValidationError):
        ChunkCreate(speaker="Alice", start_ts=-1, end_ts=10, text="hi", chunk_index=0)
