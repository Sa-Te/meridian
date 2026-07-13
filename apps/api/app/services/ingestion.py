import re
from datetime import date as date_type

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chunk, Meeting
from app.providers.embedding.base import EmbeddingProvider
from app.repositories.meeting_repository import MeetingRepository
from app.services.chunking import chunk_turns
from app.services.transcript_parser import SpeakerTurn, parse_transcript

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


async def _ingest_turns(
    *,
    filename: str,
    raw_text: str,
    turns: list[SpeakerTurn],
    embedding_provider: EmbeddingProvider,
    session: AsyncSession,
) -> Meeting:
    """Shared chunk -> embed -> store core for both ingest_transcript
    (hand-typed text, turns from parse_transcript) and
    ingest_audio_transcript (turns from app/services/audio_alignment.py).
    See docs/adr/0006 for the chunking approach and docs/adr/0012 for why
    the audio path builds SpeakerTurn objects directly instead of
    round-tripping through raw_text and parse_transcript.
    """
    title, meeting_date = derive_meeting_metadata(filename)
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


async def ingest_transcript(
    *,
    filename: str,
    raw_text: str,
    embedding_provider: EmbeddingProvider,
    session: AsyncSession,
) -> Meeting:
    """Parse -> chunk -> embed -> store a hand-typed transcript end to end.

    See docs/adr/0006 for the chunking approach and app/services/chunking.py
    and app/services/transcript_parser.py for the two independently testable
    stages this composes, per ADR-0003.
    """
    turns = parse_transcript(raw_text)
    return await _ingest_turns(
        filename=filename,
        raw_text=raw_text,
        turns=turns,
        embedding_provider=embedding_provider,
        session=session,
    )


def _serialize_turns(turns: list[SpeakerTurn]) -> str:
    """Renders turns back into the "[HH:MM:SS] Speaker: text" display
    format used by hand-typed transcripts, for Meeting.raw_text -- a
    human-readable record of what was actually transcribed, never
    re-parsed (see ingest_audio_transcript)."""
    lines = []
    for turn in turns:
        hours, remainder = divmod(turn.start_ts, 3600)
        minutes, seconds = divmod(remainder, 60)
        lines.append(f"[{hours:02d}:{minutes:02d}:{seconds:02d}] {turn.speaker}: {turn.text}")
    return "\n".join(lines)


async def ingest_audio_transcript(
    *,
    filename: str,
    turns: list[SpeakerTurn],
    embedding_provider: EmbeddingProvider,
    session: AsyncSession,
) -> Meeting:
    """Chunk -> embed -> store an already-transcribed-and-diarized audio
    meeting (app/services/audio_alignment.py's aligned output), reusing the
    exact same chunk -> embed -> store core as ingest_transcript. See
    docs/adr/0012.

    Unlike ingest_transcript, there is no raw_text to parse: turns already
    carry real per-segment start/end timestamps from transcription and
    diarization. Round-tripping them through parse_transcript's
    "[HH:MM:SS] Speaker: text" format first would discard that precision --
    the format only carries one timestamp per turn, reconstructing end_ts
    as the *next* turn's start_ts (see SpeakerTurn's docstring), which is
    only a reasonable approximation for a transcript that never had real
    end timestamps to begin with. Meeting.raw_text is still populated, with
    a human-readable rendering of these turns for display and idempotent
    re-ingest lookups, just never re-parsed.
    """
    raw_text = _serialize_turns(turns)
    return await _ingest_turns(
        filename=filename,
        raw_text=raw_text,
        turns=turns,
        embedding_provider=embedding_provider,
        session=session,
    )
