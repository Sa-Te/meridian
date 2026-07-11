from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.dependencies import get_cached_embedding_provider, get_cached_llm_provider
from app.models.schemas import AskRequest, AskResponse, CitationRead
from app.providers.embedding.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.meeting_repository import MeetingRepository
from app.services.answer_generation import UNSUPPORTED_ANSWER, generate_answer
from app.services.guardrails.output_guardrail import passes_retrieval_confidence
from app.services.retrieval import hybrid_search

router = APIRouter(tags=["ask"])


async def _ask(
    *,
    question: str,
    meeting_id: UUID | None,
    session: AsyncSession,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    settings: Settings,
) -> AskResponse:
    query_embedding = (await embedding_provider.embed([question]))[0]
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
    if not passes_retrieval_confidence(
        retrieved, threshold=settings.retrieval_confidence_threshold
    ):
        return AskResponse(answer=UNSUPPORTED_ANSWER, supported=False, citations=[])

    chunks_by_id = {r.chunk.id: r.chunk for r in retrieved}

    result = await generate_answer(
        question=question,
        retrieved_chunks=[retrieved_chunk.chunk for retrieved_chunk in retrieved],
        llm_provider=llm_provider,
    )

    citations = [
        CitationRead(
            chunk_id=chunk.id,
            meeting_id=chunk.meeting_id,
            speaker=chunk.speaker,
            start_ts=chunk.start_ts,
            end_ts=chunk.end_ts,
        )
        for citation in result.citations
        if (chunk := chunks_by_id.get(citation.chunk_id)) is not None
    ]
    return AskResponse(answer=result.answer, supported=result.supported, citations=citations)


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
    )
