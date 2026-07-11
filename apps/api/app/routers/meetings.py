from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.dependencies import get_cached_embedding_provider, get_cached_llm_provider
from app.models.schemas import (
    ActionItemRead,
    DecisionRead,
    IngestResponse,
    PromptInjectionFindingRead,
)
from app.providers.embedding.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.repositories.meeting_repository import MeetingRepository
from app.services.extraction import extract_records, to_orm_action_items, to_orm_decisions
from app.services.guardrails.input_guardrail import scan_chunks_for_prompt_injection
from app.services.ingestion import ingest_transcript

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_meeting(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_cached_embedding_provider),
    llm_provider: LLMProvider = Depends(get_cached_llm_provider),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    raw_bytes = await file.read()
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Transcript file must be UTF-8 text.") from exc

    try:
        meeting = await ingest_transcript(
            filename=file.filename or "transcript.txt",
            raw_text=raw_text,
            embedding_provider=embedding_provider,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    injection_findings = scan_chunks_for_prompt_injection(meeting.chunks)

    extraction_result = await extract_records(
        meeting_chunks=meeting.chunks,
        llm_provider=llm_provider,
        confidence_threshold=settings.extraction_confidence_threshold,
    )
    await MeetingRepository(session).add_extractions(
        meeting,
        decisions=to_orm_decisions(extraction_result.decisions),
        action_items=to_orm_action_items(extraction_result.action_items),
    )

    return IngestResponse(
        meeting_id=meeting.id,
        chunk_count=len(meeting.chunks),
        decision_count=len(extraction_result.decisions),
        action_item_count=len(extraction_result.action_items),
        flagged_for_prompt_injection=bool(injection_findings),
        prompt_injection_findings=[
            PromptInjectionFindingRead(
                chunk_index=finding.chunk_index,
                pattern=finding.pattern_name,
                matched_text=finding.matched_text,
            )
            for finding in injection_findings
        ],
    )


@router.get("/{meeting_id}/decisions", response_model=list[DecisionRead])
async def get_meeting_decisions(
    meeting_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[DecisionRead]:
    meeting = await MeetingRepository(session).get_by_id(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return [DecisionRead.model_validate(decision) for decision in meeting.decisions]


@router.get("/{meeting_id}/action-items", response_model=list[ActionItemRead])
async def get_meeting_action_items(
    meeting_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ActionItemRead]:
    meeting = await MeetingRepository(session).get_by_id(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return [ActionItemRead.model_validate(item) for item in meeting.action_items]
