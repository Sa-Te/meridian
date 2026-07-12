import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.orm import ActionItemStatus, TraceOutcome


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


class MeetingSummaryRead(BaseModel):
    """Lighter-weight Meeting shape for GET /meetings and GET /meetings/{id}
    (Phase 7's meeting picker) -- deliberately omits raw_text, which is
    irrelevant to a list/header view and can be a whole transcript's worth
    of text per meeting.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    date: date
    participants: list[str]
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


class CitationRead(BaseModel):
    """A single supporting chunk cited in an AskResponse, or the chunk a
    Decision/ActionItem was extracted from. Every field is looked up
    server-side from the actual chunk, never taken from the LLM's response
    -- see docs/adr/0007. Includes the chunk's own text (Phase 7) so a
    citation can be rendered/expanded inline without a second request."""

    chunk_id: uuid.UUID
    meeting_id: uuid.UUID
    speaker: str
    start_ts: int
    end_ts: int
    text: str


class DecisionCreate(BaseModel):
    """Fields required to record an extracted Decision. See docs/adr/0005 for why
    source_chunk_id is required rather than optional."""

    text: str
    source_chunk_id: uuid.UUID
    confidence: float = Field(ge=0.0, le=1.0)


class DecisionRead(BaseModel):
    """API response shape for a Decision. source_citation (Phase 7) is
    built server-side from the Decision's source_chunk_id/source_chunk
    relationship at the router, not auto-mapped from the ORM object --
    see app/routers/meetings.py.
    """

    id: uuid.UUID
    meeting_id: uuid.UUID
    text: str
    source_citation: CitationRead
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
    """API response shape for an ActionItem. See DecisionRead's docstring --
    same source_citation construction reasoning."""

    id: uuid.UUID
    meeting_id: uuid.UUID
    text: str
    owner: str | None
    due_date: date | None
    source_citation: CitationRead
    confidence: float
    status: ActionItemStatus
    created_at: datetime


class PromptInjectionFindingRead(BaseModel):
    """One prompt-injection-style match found in a transcript chunk during
    ingestion's input guardrail scan. See docs/adr/0008."""

    chunk_index: int
    pattern: str
    matched_text: str


class IngestResponse(BaseModel):
    """Response shape for POST /meetings/ingest."""

    meeting_id: uuid.UUID
    chunk_count: int
    decision_count: int
    action_item_count: int
    flagged_for_prompt_injection: bool
    prompt_injection_findings: list[PromptInjectionFindingRead]


class AskRequest(BaseModel):
    """Request body for POST /ask and POST /meetings/{id}/ask."""

    question: str = Field(min_length=1)


class AskResponse(BaseModel):
    """Response shape for POST /ask and POST /meetings/{id}/ask."""

    answer: str
    supported: bool
    citations: list[CitationRead]


class SearchResultRead(BaseModel):
    """One ranked chunk from GET /search, backing the MCP search_meetings
    tool (docs/adr/0011). fused_score is hybrid_search's ranking score
    (see app/services/retrieval.py) -- higher is a better match, not a
    calibrated probability."""

    citation: CitationRead
    fused_score: float


class SearchResponse(BaseModel):
    """Response shape for GET /search."""

    results: list[SearchResultRead]


class TraceStageRead(BaseModel):
    """One recorded stage within a Trace. See docs/adr/0010."""

    name: str
    started_at: datetime
    duration_ms: float
    metadata: dict[str, Any]


class TraceRead(BaseModel):
    """API response shape for a Trace. See docs/adr/0010."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    endpoint: str
    stages: list[TraceStageRead]
    total_duration_ms: float
    input_tokens: int
    output_tokens: int
    models_used: list[str]
    outcome: TraceOutcome
    created_at: datetime


class TraceListResponse(BaseModel):
    """Response shape for GET /traces: one page of traces plus enough to
    page further."""

    items: list[TraceRead]
    total: int
    limit: int
    offset: int
