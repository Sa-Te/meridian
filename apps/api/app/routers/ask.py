from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.dependencies import get_cached_embedding_provider, get_cached_llm_provider
from app.models.orm import TraceOutcome
from app.models.schemas import AskRequest, AskResponse, CitationRead
from app.providers.embedding.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.providers.llm.factory import get_configured_model_name
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.trace_repository import TraceRepository
from app.services.answer_generation import UNSUPPORTED_ANSWER, generate_answer
from app.services.guardrails.output_guardrail import passes_retrieval_confidence
from app.services.retrieval import hybrid_search
from app.services.tracing import TraceRecorder, TracingEmbeddingProvider, TracingLLMProvider

router = APIRouter(tags=["ask"])


async def _ask(
    *,
    question: str,
    meeting_id: UUID | None,
    session: AsyncSession,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    settings: Settings,
    endpoint: str,
) -> AskResponse:
    """See docs/adr/0010 for the tracing approach: embedding_provider and
    llm_provider are wrapped in tracing decorators before use, so
    hybrid_search/generate_answer (unchanged) automatically produce
    "embed"/"llm_generate" stages on `recorder` without knowing tracing
    exists. The trace is always persisted in `finally`, whether this
    returns normally or an exception propagates.
    """
    recorder = TraceRecorder(endpoint=endpoint)
    traced_embedding_provider = TracingEmbeddingProvider(embedding_provider, recorder)
    traced_llm_provider = TracingLLMProvider(
        llm_provider, recorder, model_name=get_configured_model_name(settings)
    )
    outcome = TraceOutcome.ERROR
    try:
        query_embedding = (await traced_embedding_provider.embed([question]))[0]

        async with recorder.stage(
            "hybrid_search",
            top_k=settings.retrieval_top_k,
            candidate_pool_size=settings.retrieval_candidate_pool_size,
        ) as stage_metadata:
            retrieved = await hybrid_search(
                query_text=question,
                query_embedding=query_embedding,
                chunk_repository=ChunkRepository(session),
                meeting_id=meeting_id,
                top_k=settings.retrieval_top_k,
                candidate_pool_size=settings.retrieval_candidate_pool_size,
                vector_weight=settings.retrieval_vector_weight,
                text_weight=settings.retrieval_text_weight,
            )
            stage_metadata["retrieved_count"] = len(retrieved)

        async with recorder.stage("guardrail_confidence_check") as stage_metadata:
            confidence_ok = passes_retrieval_confidence(
                retrieved, threshold=settings.retrieval_confidence_threshold
            )
            stage_metadata["passed"] = confidence_ok

        if not confidence_ok:
            outcome = TraceOutcome.DECLINED
            return AskResponse(answer=UNSUPPORTED_ANSWER, supported=False, citations=[])

        chunks_by_id = {r.chunk.id: r.chunk for r in retrieved}

        async with recorder.stage("generate_answer") as stage_metadata:
            result = await generate_answer(
                question=question,
                retrieved_chunks=[retrieved_chunk.chunk for retrieved_chunk in retrieved],
                llm_provider=traced_llm_provider,
            )
            stage_metadata["supported"] = result.supported
            stage_metadata["citation_count"] = len(result.citations)

        citations = [
            CitationRead(
                chunk_id=chunk.id,
                meeting_id=chunk.meeting_id,
                speaker=chunk.speaker,
                start_ts=chunk.start_ts,
                end_ts=chunk.end_ts,
                text=chunk.text,
            )
            for citation in result.citations
            if (chunk := chunks_by_id.get(citation.chunk_id)) is not None
        ]
        outcome = TraceOutcome.ANSWERED if result.supported else TraceOutcome.DECLINED
        return AskResponse(answer=result.answer, supported=result.supported, citations=citations)
    finally:
        await TraceRepository(session).create(recorder.to_orm(outcome=outcome))


@router.post("/meetings/{meeting_id}/ask", response_model=AskResponse)
async def ask_meeting(
    meeting_id: UUID,
    request: AskRequest,
    session: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_cached_embedding_provider),
    llm_provider: LLMProvider = Depends(get_cached_llm_provider),
    settings: Settings = Depends(get_settings),
) -> AskResponse:
    meeting = await MeetingRepository(session).get_by_id(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")

    return await _ask(
        question=request.question,
        meeting_id=meeting_id,
        session=session,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        settings=settings,
        endpoint="POST /meetings/{meeting_id}/ask",
    )


@router.post("/ask", response_model=AskResponse)
async def ask_global(
    request: AskRequest,
    session: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_cached_embedding_provider),
    llm_provider: LLMProvider = Depends(get_cached_llm_provider),
    settings: Settings = Depends(get_settings),
) -> AskResponse:
    return await _ask(
        question=request.question,
        meeting_id=None,
        session=session,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        settings=settings,
        endpoint="POST /ask",
    )
