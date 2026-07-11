from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_cached_embedding_provider
from app.models.schemas import IngestResponse
from app.providers.embedding.base import EmbeddingProvider
from app.services.ingestion import ingest_transcript

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_meeting(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_cached_embedding_provider),
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

    return IngestResponse(meeting_id=meeting.id, chunk_count=len(meeting.chunks))
