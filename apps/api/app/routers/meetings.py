from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.dependencies import (
    get_cached_diarization_provider,
    get_cached_embedding_provider,
    get_cached_llm_provider,
    get_cached_transcription_provider,
)
from app.models.orm import Meeting, TraceOutcome
from app.models.schemas import (
    ActionItemRead,
    DecisionRead,
    IngestResponse,
    MeetingSummaryRead,
    PromptInjectionFindingRead,
)
from app.providers.diarization.base import DiarizationProvider
from app.providers.embedding.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.providers.llm.factory import get_configured_model_name
from app.providers.transcription.base import TranscriptionProvider
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.trace_repository import TraceRepository
from app.services.audio_ingestion import ingest_audio
from app.services.citations import build_citation
from app.services.extraction import extract_records, to_orm_action_items, to_orm_decisions
from app.services.guardrails.input_guardrail import scan_chunks_for_prompt_injection
from app.services.ingestion import derive_meeting_metadata, ingest_transcript
from app.services.tracing import (
    TraceRecorder,
    TracingDiarizationProvider,
    TracingEmbeddingProvider,
    TracingLLMProvider,
    TracingTranscriptionProvider,
)

router = APIRouter(prefix="/meetings", tags=["meetings"])

_ALLOWED_AUDIO_EXTENSIONS = {".wav", ".flac"}


async def _finish_ingest(
    meeting: Meeting,
    *,
    recorder: TraceRecorder,
    llm_provider: LLMProvider,
    settings: Settings,
    session: AsyncSession,
) -> IngestResponse:
    """Shared post-ingestion pipeline for both ingest_meeting (text) and
    ingest_audio_meeting (audio): prompt-injection scan -> structured
    extraction -> persistence -> response. Both callers pass an
    already-tracing-wrapped llm_provider, so the "llm_generate_structured"
    stage this triggers via extract_records is recorded automatically --
    see app/services/tracing.py.
    """
    async with recorder.stage("prompt_injection_scan") as stage_metadata:
        injection_findings = scan_chunks_for_prompt_injection(meeting.chunks)
        stage_metadata["flagged"] = bool(injection_findings)
        stage_metadata["finding_count"] = len(injection_findings)

    async with recorder.stage("extract_records") as stage_metadata:
        extraction_result = await extract_records(
            meeting_chunks=meeting.chunks,
            llm_provider=llm_provider,
            confidence_threshold=settings.extraction_confidence_threshold,
        )
        stage_metadata["decision_count"] = len(extraction_result.decisions)
        stage_metadata["action_item_count"] = len(extraction_result.action_items)

    async with recorder.stage("persist_extractions"):
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


@router.post("/ingest", response_model=IngestResponse)
async def ingest_meeting(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_cached_embedding_provider),
    llm_provider: LLMProvider = Depends(get_cached_llm_provider),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    """See docs/adr/0010 for the tracing approach -- same pattern as
    app/routers/ask.py's _ask: embedding_provider/llm_provider are wrapped
    in tracing decorators before use, so ingest_transcript/extract_records
    (unchanged) produce "embed"/"llm_generate_structured" stages for free.
    No trace is created for a request that fails before real processing
    starts (a bad file encoding) -- tracing measures processing, not input
    validation.
    """
    raw_bytes = await file.read()
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Transcript file must be UTF-8 text.") from exc

    recorder = TraceRecorder(endpoint="POST /meetings/ingest")
    traced_embedding_provider = TracingEmbeddingProvider(embedding_provider, recorder)
    traced_llm_provider = TracingLLMProvider(
        llm_provider, recorder, model_name=get_configured_model_name(settings)
    )
    outcome = TraceOutcome.ERROR
    try:
        async with recorder.stage("ingest_transcript", filename=file.filename) as stage_metadata:
            try:
                meeting = await ingest_transcript(
                    filename=file.filename or "transcript.txt",
                    raw_text=raw_text,
                    embedding_provider=traced_embedding_provider,
                    session=session,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            stage_metadata["chunk_count"] = len(meeting.chunks)

        response = await _finish_ingest(
            meeting,
            recorder=recorder,
            llm_provider=traced_llm_provider,
            settings=settings,
            session=session,
        )
        outcome = TraceOutcome.ANSWERED
        return response
    finally:
        await TraceRepository(session).create(recorder.to_orm(outcome=outcome))


@router.post("/ingest-audio", response_model=IngestResponse)
async def ingest_audio_meeting(
    file: UploadFile = File(...),
    min_speakers: int | None = Query(
        default=None,
        ge=1,
        description="Optional hint if the caller already knows roughly how many "
        "distinct speakers to expect. Unconstrained (auto-detected) when omitted.",
    ),
    max_speakers: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_cached_embedding_provider),
    llm_provider: LLMProvider = Depends(get_cached_llm_provider),
    transcription_provider: TranscriptionProvider = Depends(get_cached_transcription_provider),
    diarization_provider: DiarizationProvider = Depends(get_cached_diarization_provider),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    """Transcribe + diarize an audio recording and ingest it exactly like a
    hand-typed transcript -- see docs/adr/0012 for the transcription/
    diarization stack, the alignment policy, and its edge-case handling.

    Same tracing pattern as ingest_meeting (see docs/adr/0010): every
    provider is wrapped before use, so transcribe/diarize/embed/
    llm_generate_structured stages are all recorded automatically. The
    shared _finish_ingest pipeline (prompt-injection scan, extraction,
    persistence) is identical to the text path -- audio is a different
    front door onto the exact same Phase 2 pipeline, not a parallel one.
    """
    filename = file.filename or "recording.wav"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in _ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported audio format {extension or '(none)'!r}. Supported: "
            f"{', '.join(sorted(_ALLOWED_AUDIO_EXTENSIONS))}.",
        )
    # Checked here, before transcribing/diarizing, not left to surface only
    # once _ingest_turns gets around to calling this same function: a real
    # transcribe+diarize pass over even a short recording takes tens of
    # seconds, and a bad filename is exactly the kind of cheap check that
    # should fail fast rather than after paying for that work first.
    try:
        derive_meeting_metadata(filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    audio_bytes = await file.read()

    recorder = TraceRecorder(endpoint="POST /meetings/ingest-audio")
    traced_embedding_provider = TracingEmbeddingProvider(embedding_provider, recorder)
    traced_llm_provider = TracingLLMProvider(
        llm_provider, recorder, model_name=get_configured_model_name(settings)
    )
    traced_transcription_provider = TracingTranscriptionProvider(transcription_provider, recorder)
    traced_diarization_provider = TracingDiarizationProvider(diarization_provider, recorder)
    outcome = TraceOutcome.ERROR
    try:
        async with recorder.stage("ingest_audio", filename=filename) as stage_metadata:
            try:
                meeting = await ingest_audio(
                    filename=filename,
                    audio_bytes=audio_bytes,
                    transcription_provider=traced_transcription_provider,
                    diarization_provider=traced_diarization_provider,
                    embedding_provider=traced_embedding_provider,
                    session=session,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            stage_metadata["chunk_count"] = len(meeting.chunks)

        response = await _finish_ingest(
            meeting,
            recorder=recorder,
            llm_provider=traced_llm_provider,
            settings=settings,
            session=session,
        )
        outcome = TraceOutcome.ANSWERED
        return response
    finally:
        await TraceRepository(session).create(recorder.to_orm(outcome=outcome))


@router.get("", response_model=list[MeetingSummaryRead])
async def list_meetings(session: AsyncSession = Depends(get_db)) -> list[MeetingSummaryRead]:
    meetings = await MeetingRepository(session).list_all()
    return [MeetingSummaryRead.model_validate(meeting) for meeting in meetings]


@router.get("/{meeting_id}", response_model=MeetingSummaryRead)
async def get_meeting(
    meeting_id: UUID, session: AsyncSession = Depends(get_db)
) -> MeetingSummaryRead:
    meeting = await MeetingRepository(session).get_by_id(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return MeetingSummaryRead.model_validate(meeting)


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: UUID, session: AsyncSession = Depends(get_db)) -> None:
    repository = MeetingRepository(session)
    meeting = await repository.get_by_id(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    await repository.delete(meeting)


@router.get("/{meeting_id}/decisions", response_model=list[DecisionRead])
async def get_meeting_decisions(
    meeting_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[DecisionRead]:
    meeting = await MeetingRepository(session).get_by_id(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    chunks_by_id = {chunk.id: chunk for chunk in meeting.chunks}
    return [
        DecisionRead(
            id=decision.id,
            meeting_id=decision.meeting_id,
            text=decision.text,
            source_citation=build_citation(chunks_by_id[decision.source_chunk_id]),
            confidence=decision.confidence,
            created_at=decision.created_at,
        )
        for decision in meeting.decisions
    ]


@router.get("/{meeting_id}/action-items", response_model=list[ActionItemRead])
async def get_meeting_action_items(
    meeting_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ActionItemRead]:
    meeting = await MeetingRepository(session).get_by_id(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    chunks_by_id = {chunk.id: chunk for chunk in meeting.chunks}
    return [
        ActionItemRead(
            id=item.id,
            meeting_id=item.meeting_id,
            text=item.text,
            owner=item.owner,
            due_date=item.due_date,
            source_citation=build_citation(chunks_by_id[item.source_chunk_id]),
            confidence=item.confidence,
            status=item.status,
            created_at=item.created_at,
        )
        for item in meeting.action_items
    ]
