import uuid
from datetime import date as date_type
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Output dimensionality of BAAI/bge-base-en-v1.5, the default EmbeddingProvider
# per ADR-0004. Populated starting in Phase 2; nullable until then.
EMBEDDING_DIMENSIONS = 768


class Base(DeclarativeBase):
    pass


class ActionItemStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Meeting(Base):
    """A single ingested transcript and its metadata. See docs/adr/0005."""

    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    participants: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", order_by="Chunk.chunk_index"
    )
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """A single speaker turn (or turn fragment) within a Meeting.

    start_ts/end_ts are elapsed seconds from the start of the meeting (the
    transcripts encode elapsed-time markers like [00:03:12], not wall-clock
    timestamps) -- see docs/adr/0005.
    """

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("meeting_id", "chunk_index", name="uq_chunks_meeting_id_chunk_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    speaker: Mapped[str] = mapped_column(String(255), nullable=False)
    start_ts: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ts: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # DB-generated from `text` (see the Phase 3 migration); never set by the
    # ORM. Powers the full-text side of hybrid retrieval -- see ADR-0007.
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', text)", persisted=True), nullable=True
    )

    meeting: Mapped["Meeting"] = relationship(back_populates="chunks")
    # passive_deletes=True: don't have the ORM try to null out source_chunk_id
    # (it's NOT NULL) when a chunk is deleted -- let the DB's ON DELETE CASCADE
    # on that FK remove the citing Decision/ActionItem rows instead.
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="source_chunk", passive_deletes=True
    )
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="source_chunk", passive_deletes=True
    )


class Decision(Base):
    """A decision extracted from a meeting, grounded in one source chunk.

    source_chunk_id is required, not optional, and cascades on delete -- see
    docs/adr/0005 for why an uncited decision is treated as an invalid state
    rather than an allowed one.
    """

    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_decisions_confidence_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    meeting: Mapped["Meeting"] = relationship(back_populates="decisions")
    source_chunk: Mapped["Chunk"] = relationship(back_populates="decisions")


class ActionItem(Base):
    """An action item extracted from a meeting, grounded in one source chunk.

    Same source_chunk_id reasoning as Decision -- see docs/adr/0005.
    """

    __tablename__ = "action_items"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_action_items_confidence_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[ActionItemStatus] = mapped_column(
        Enum(
            ActionItemStatus,
            name="action_item_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ActionItemStatus.OPEN,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    meeting: Mapped["Meeting"] = relationship(back_populates="action_items")
    source_chunk: Mapped["Chunk"] = relationship(back_populates="action_items")


class TraceOutcome(StrEnum):
    ANSWERED = "answered"
    DECLINED = "declined"
    ERROR = "error"


class Trace(Base):
    """A structured record of one traced request: the ask flow (Phase 3) or
    the ingest+extraction flow (Phase 2/4). See docs/adr/0010.

    There is no separate "request id" field -- a Trace row corresponds 1:1
    to one request, so its own primary key already serves that purpose.

    stages is a JSONB list of {name, started_at, duration_ms, metadata}
    dicts rather than a normalized child table -- see docs/adr/0010 for why
    a handful of stages per request doesn't earn its own table.
    """

    __tablename__ = "traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    total_duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Every model actually invoked while producing this trace -- see
    # docs/adr/0010 for why this is populated even for generate_structured
    # calls (extraction), which unlike generate() carry no per-call usage.
    models_used: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    outcome: Mapped[TraceOutcome] = mapped_column(
        Enum(
            TraceOutcome,
            name="trace_outcome",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
