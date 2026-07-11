import re
from datetime import date as date_type

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chunk, Meeting
from app.providers.embedding.base import EmbeddingProvider
from app.repositories.meeting_repository import MeetingRepository
from app.services.chunking import chunk_turns
from app.services.transcript_parser import parse_transcript

_FILENAME_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(.+)$")


def derive_meeting_metadata(filename: str) -> tuple[str, date_type]:
    """Derive a title and date from a transcript filename shaped like
    "YYYY-MM-DD_slug-title.txt" -- the convention used under
    data/transcripts/, and expected for uploads to POST /meetings/ingest.
    Real, explicit per-meeting metadata entry is out of scope for this
    phase; see ROADMAP.md.
    """
    stem = filename.rsplit(".", 1)[0]
    match = _FILENAME_PATTERN.match(stem)
    if match is None:
        raise ValueError(
            f"Transcript filename does not match the expected YYYY-MM-DD_slug pattern: {filename}"
        )
    year, month, day, slug = match.groups()
    title = slug.replace("-", " ").title()
    return title, date_type(int(year), int(month), int(day))


async def ingest_transcript(
    *,
    filename: str,
    raw_text: str,
    embedding_provider: EmbeddingProvider,
    session: AsyncSession,
) -> Meeting:
    """Parse -> chunk -> embed -> store a transcript end to end.

    See docs/adr/0006 for the chunking approach and app/services/chunking.py
    and app/services/transcript_parser.py for the two independently testable
    stages this composes, per ADR-0003.
    """
    title, meeting_date = derive_meeting_metadata(filename)
    turns = parse_transcript(raw_text)
    participants = sorted({turn.speaker for turn in turns})

    chunk_data = chunk_turns(turns)
    embeddings = (
        await embedding_provider.embed([chunk.text for chunk in chunk_data]) if chunk_data else []
    )

    chunks = [
        Chunk(
            speaker=data.speaker,
            start_ts=data.start_ts,
            end_ts=data.end_ts,
            text=data.text,
            embedding=embedding,
            chunk_index=index,
        )
        for index, (data, embedding) in enumerate(zip(chunk_data, embeddings, strict=True))
    ]

    meeting = Meeting(
        title=title,
        date=meeting_date,
        participants=participants,
        source_filename=filename,
        raw_text=raw_text,
        chunks=chunks,
    )

    return await MeetingRepository(session).create(meeting)
