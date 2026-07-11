import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.orm import ActionItemStatus


class MeetingCreate(BaseModel):
    """Fields required to register a new Meeting. See docs/adr/0005."""

    title: str
    date: date
    participants: list[str]
    source_filename: str
    raw_text: str


class MeetingRead(BaseModel):
    """API response shape for a Meeting. Never the ORM object directly."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    date: date
    participants: list[str]
    source_filename: str
    raw_text: str
    created_at: datetime


class ChunkCreate(BaseModel):
    """Fields required to create a Chunk. Embedding is populated in Phase 2."""

    speaker: str
    start_ts: int = Field(ge=0, description="Elapsed seconds from the start of the meeting.")
    end_ts: int = Field(ge=0, description="Elapsed seconds from the start of the meeting.")
    text: str
    chunk_index: int = Field(ge=0)


class ChunkRead(BaseModel):
    """API response shape for a Chunk. Embedding vector is not exposed to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    speaker: str
    start_ts: int
    end_ts: int
    text: str
    chunk_index: int


class DecisionCreate(BaseModel):
    """Fields required to record an extracted Decision. See docs/adr/0005 for why
    source_chunk_id is required rather than optional."""

    text: str
    source_chunk_id: uuid.UUID
    confidence: float = Field(ge=0.0, le=1.0)


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    text: str
    source_chunk_id: uuid.UUID
    confidence: float
    created_at: datetime


class ActionItemCreate(BaseModel):
    """Fields required to record an extracted ActionItem."""

    text: str
    owner: str | None = None
    due_date: date | None = None
    source_chunk_id: uuid.UUID
    confidence: float = Field(ge=0.0, le=1.0)
    status: ActionItemStatus = ActionItemStatus.OPEN


class ActionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    text: str
    owner: str | None
    due_date: date | None
    source_chunk_id: uuid.UUID
    confidence: float
    status: ActionItemStatus
    created_at: datetime


class IngestResponse(BaseModel):
    """Response shape for POST /meetings/ingest."""

    meeting_id: uuid.UUID
    chunk_count: int
