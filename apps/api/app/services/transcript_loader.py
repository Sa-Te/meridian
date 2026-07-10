import re
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path

from app.models.orm import Chunk, Meeting

_TURN_PATTERN = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]\s*([^:]+):\s*(.*)$")
_FILENAME_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(.+)$")


@dataclass
class _ParsedTurn:
    speaker: str
    start_ts: int
    text_lines: list[str] = field(default_factory=list)


def _seconds(hours: str, minutes: str, seconds: str) -> int:
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)


def parse_transcript_turns(raw_text: str) -> list[tuple[str, int, str]]:
    """Naive speaker-turn parse: "[HH:MM:SS] Speaker: text", with unmarked
    continuation lines appended to the turn currently being built.

    This is a Phase 1 placeholder, just precise enough to prove the domain
    schema round-trips end to end. It deliberately does not handle the edge
    cases (malformed lines, missing timestamps, etc.) that Phase 2's real
    parser is scoped to handle -- see ROADMAP.md Phase 2.

    Returns (speaker, start_ts_seconds, text) tuples in transcript order.
    """
    turns: list[_ParsedTurn] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _TURN_PATTERN.match(line)
        if match is not None:
            hours, minutes, seconds, speaker, text = match.groups()
            turns.append(
                _ParsedTurn(
                    speaker=speaker.strip(),
                    start_ts=_seconds(hours, minutes, seconds),
                    text_lines=[text.strip()],
                )
            )
        elif turns:
            turns[-1].text_lines.append(line)

    return [(turn.speaker, turn.start_ts, " ".join(turn.text_lines)) for turn in turns]


def build_meeting_from_transcript(
    *,
    title: str,
    meeting_date: date_type,
    participants: list[str],
    source_filename: str,
    raw_text: str,
) -> Meeting:
    """Build an unpersisted Meeting with placeholder Chunks (no embeddings --
    that's Phase 2) from raw transcript text, one Chunk per parsed speaker
    turn. A turn's end_ts is the next turn's start_ts (or its own start_ts if
    it's the last turn in the transcript, since no true end timestamp is
    available yet)."""
    turns = parse_transcript_turns(raw_text)
    chunks = [
        Chunk(
            speaker=speaker,
            start_ts=start_ts,
            end_ts=turns[index + 1][1] if index + 1 < len(turns) else start_ts,
            text=text,
            chunk_index=index,
        )
        for index, (speaker, start_ts, text) in enumerate(turns)
    ]
    return Meeting(
        title=title,
        date=meeting_date,
        participants=participants,
        source_filename=source_filename,
        raw_text=raw_text,
        chunks=chunks,
    )


def meeting_metadata_from_filename(path: Path) -> tuple[str, date_type]:
    """Derive a title and date from a transcript filename shaped like
    "YYYY-MM-DD_slug-title.txt" (the convention used under data/transcripts/).

    This is a Phase 1 placeholder convention: real ingestion (Phase 2) will
    take title/date as explicit metadata rather than inferring them from a
    filename.
    """
    match = _FILENAME_PATTERN.match(path.stem)
    if match is None:
        raise ValueError(
            f"Transcript filename does not match the expected YYYY-MM-DD_slug pattern: {path.name}"
        )
    year, month, day, slug = match.groups()
    title = slug.replace("-", " ").title()
    return title, date_type(int(year), int(month), int(day))


def load_meeting_from_file(path: Path) -> Meeting:
    """Build an unpersisted Meeting (with placeholder Chunks) from a
    transcript file on disk. Title and date come from the filename (see
    meeting_metadata_from_filename); participants are the distinct speakers
    found in the parsed turns.
    """
    title, meeting_date = meeting_metadata_from_filename(path)
    raw_text = path.read_text()
    participants = sorted({speaker for speaker, _, _ in parse_transcript_turns(raw_text)})
    return build_meeting_from_transcript(
        title=title,
        meeting_date=meeting_date,
        participants=participants,
        source_filename=path.name,
        raw_text=raw_text,
    )
