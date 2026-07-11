"""Structured decision/action-item extraction over a meeting's stored
chunks. Runs after chunking/embedding/storage (Phase 2), so every chunk
already has a real chunk_id to cite -- see app/routers/meetings.py for where
this is invoked in the ingestion flow.

Uses LLMProvider.generate_structured (native structured output) rather than
the plain-JSON-prompt pattern from ADR-0007's answer generation: see
docs/adr/0008 for why extraction gets this treatment now, while Phase 3's
citation-enforced answers deliberately don't.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as date_type
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from app.models.orm import ActionItem, Chunk, Decision
from app.providers.llm.base import LLMProvider
from app.services.guardrails.output_guardrail import citation_ids_are_valid

_SYSTEM_PROMPT = (
    "You are Meridian, a meeting-intelligence assistant. Read the meeting "
    "transcript excerpts below and extract every explicit decision and "
    "action item.\n\n"
    "A decision is a concrete choice the group settled on, not merely a "
    "topic that was discussed. An action item is a specific task assigned "
    "to a named owner, or clearly owed by the group, with a follow-up "
    "expectation.\n\n"
    "For each one, set source_chunk_id to the chunk_id of the excerpt that "
    "most explicitly states it -- copied exactly from the [chunk_id: ...] "
    "tag shown next to that excerpt, never invented. Set confidence between "
    "0 and 1: use a high value only when the decision or action item is "
    "stated explicitly, not implied or guessed at. For an action item, set "
    "owner to the name of the person responsible if the transcript names "
    "one, otherwise null; set due_date only if an explicit calendar date is "
    'stated (not a relative phrase like "next sprint"), otherwise null.\n\n'
    "If the transcript contains no decisions, or no action items, return an "
    "empty list for that field -- do not invent one to avoid an empty "
    "response."
)

_STRICT_RETRY_SUFFIX = (
    "\n\nIMPORTANT: your previous response could not be read. Return decisions "
    "and action_items exactly matching the required schema, with every "
    "source_chunk_id copied exactly from an excerpt shown above."
)


@dataclass(frozen=True)
class ExtractedDecision:
    text: str
    source_chunk_id: UUID
    confidence: float


@dataclass(frozen=True)
class ExtractedActionItem:
    text: str
    owner: str | None
    due_date: date_type | None
    source_chunk_id: UUID
    confidence: float


@dataclass(frozen=True)
class ExtractionResult:
    decisions: list[ExtractedDecision]
    action_items: list[ExtractedActionItem]


class _LLMDecision(BaseModel):
    text: str
    source_chunk_id: UUID
    confidence: float = Field(ge=0.0, le=1.0)


class _LLMActionItem(BaseModel):
    text: str
    owner: str | None = None
    due_date: date_type | None = None
    source_chunk_id: UUID
    confidence: float = Field(ge=0.0, le=1.0)


class _LLMExtractionPayload(BaseModel):
    decisions: list[_LLMDecision]
    action_items: list[_LLMActionItem]


def _build_prompt(chunks: Sequence[Chunk]) -> str:
    excerpts = "\n\n".join(
        f"[chunk_id: {chunk.id}] [{chunk.start_ts}s] {chunk.speaker}: {chunk.text}"
        for chunk in chunks
    )
    return f"Transcript excerpts:\n\n{excerpts}"


def _filter_guardrailed(
    payload: _LLMExtractionPayload,
    *,
    valid_chunk_ids: set[UUID],
    confidence_threshold: float,
) -> ExtractionResult:
    """Per-item guardrail filter: a hallucinated/out-of-scope source_chunk_id
    or a below-threshold confidence drops only that one item. Unlike Phase
    3's all-or-nothing citation check on a single answer, one bad item in a
    batch of several correct extractions shouldn't discard the good ones --
    see docs/adr/0008.
    """
    decisions = [
        ExtractedDecision(
            text=item.text, source_chunk_id=item.source_chunk_id, confidence=item.confidence
        )
        for item in payload.decisions
        if item.confidence >= confidence_threshold
        and citation_ids_are_valid([item.source_chunk_id], valid_chunk_ids)
    ]
    action_items = [
        ExtractedActionItem(
            text=item.text,
            owner=item.owner,
            due_date=item.due_date,
            source_chunk_id=item.source_chunk_id,
            confidence=item.confidence,
        )
        for item in payload.action_items
        if item.confidence >= confidence_threshold
        and citation_ids_are_valid([item.source_chunk_id], valid_chunk_ids)
    ]
    return ExtractionResult(decisions=decisions, action_items=action_items)


async def _generate_payload(
    prompt: str, llm_provider: LLMProvider, *, system: str
) -> _LLMExtractionPayload | None:
    try:
        return await llm_provider.generate_structured(
            prompt, _LLMExtractionPayload, system=system, max_tokens=4096
        )
    except (ValidationError, ValueError):
        return None


async def extract_records(
    *,
    meeting_chunks: Sequence[Chunk],
    llm_provider: LLMProvider,
    confidence_threshold: float,
) -> ExtractionResult:
    """Extract decisions and action items from a meeting's stored chunks.

    Returns an empty ExtractionResult, without calling the LLM, when the
    meeting has no chunks. A response that fails to parse against the
    structured schema is retried once with a stricter instruction; if the
    retry also fails, this returns an empty ExtractionResult rather than
    raising -- extraction is a best-effort augmentation, and the meeting
    and its chunks are already safely stored regardless (see docs/adr/0008).
    """
    if not meeting_chunks:
        return ExtractionResult(decisions=[], action_items=[])

    valid_chunk_ids = {chunk.id for chunk in meeting_chunks}
    prompt = _build_prompt(meeting_chunks)

    payload = await _generate_payload(prompt, llm_provider, system=_SYSTEM_PROMPT)
    if payload is None:
        payload = await _generate_payload(
            prompt, llm_provider, system=_SYSTEM_PROMPT + _STRICT_RETRY_SUFFIX
        )
    if payload is None:
        return ExtractionResult(decisions=[], action_items=[])

    return _filter_guardrailed(
        payload, valid_chunk_ids=valid_chunk_ids, confidence_threshold=confidence_threshold
    )


def to_orm_decisions(decisions: Sequence[ExtractedDecision]) -> list[Decision]:
    return [
        Decision(text=item.text, source_chunk_id=item.source_chunk_id, confidence=item.confidence)
        for item in decisions
    ]


def to_orm_action_items(action_items: Sequence[ExtractedActionItem]) -> list[ActionItem]:
    return [
        ActionItem(
            text=item.text,
            owner=item.owner,
            due_date=item.due_date,
            source_chunk_id=item.source_chunk_id,
            confidence=item.confidence,
        )
        for item in action_items
    ]
