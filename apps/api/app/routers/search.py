from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.dependencies import get_cached_embedding_provider
from app.models.schemas import SearchResponse, SearchResultRead
from app.providers.embedding.base import EmbeddingProvider
from app.repositories.chunk_repository import ChunkRepository
from app.services.citations import build_citation
from app.services.retrieval import hybrid_search

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search_meetings(
    query: str = Query(min_length=1),
    top_k: int | None = Query(default=None, ge=1, le=50),
    meeting_id: UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_cached_embedding_provider),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    """Raw hybrid-search results (see app/services/retrieval.py), ranked by
    fused score, with no LLM generation step -- the retrieval half of the
    ask flow (app/routers/ask.py) exposed on its own so a caller (e.g. the
    MCP search_meetings tool, docs/adr/0011) can inspect matching chunks
    directly. Not traced: ADR-0010 scopes tracing to the ask and ingest
    flows' LLM/embedding cost specifically; this endpoint's single embed
    call doesn't warrant extending that scope.
    """
    effective_top_k = top_k if top_k is not None else settings.retrieval_top_k
    query_embedding = (await embedding_provider.embed([query]))[0]
    retrieved = await hybrid_search(
        query_text=query,
        query_embedding=query_embedding,
        chunk_repository=ChunkRepository(session),
        meeting_id=meeting_id,
        top_k=effective_top_k,
        candidate_pool_size=settings.retrieval_candidate_pool_size,
        vector_weight=settings.retrieval_vector_weight,
        text_weight=settings.retrieval_text_weight,
    )
    return SearchResponse(
        results=[
            SearchResultRead(
                citation=build_citation(retrieved_chunk.chunk),
                fused_score=retrieved_chunk.fused_score,
            )
            for retrieved_chunk in retrieved
        ]
    )
