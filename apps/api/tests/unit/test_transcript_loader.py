from datetime import date
from pathlib import Path

import pytest

from app.services.transcript_loader import (
    build_meeting_from_transcript,
    load_meeting_from_file,
    meeting_metadata_from_filename,
    parse_transcript_turns,
)


def test_parse_transcript_turns_basic() -> None:
    raw = "[00:00:05] Alice: Hello there.\n[00:01:10] Bob: Hi Alice.\n"

    turns = parse_transcript_turns(raw)

    assert turns == [("Alice", 5, "Hello there."), ("Bob", 70, "Hi Alice.")]


def test_parse_transcript_turns_joins_continuation_lines() -> None:
    raw = "[00:00:05] Alice: Hello there,\nstill talking.\n[00:00:20] Bob: Okay.\n"

    turns = parse_transcript_turns(raw)

    assert turns[0] == ("Alice", 5, "Hello there, still talking.")
    assert turns[1] == ("Bob", 20, "Okay.")


def test_parse_transcript_turns_ignores_blank_lines_and_leading_non_turn_text() -> None:
    raw = "\n   \nSome header nobody parses\n[00:00:05] Alice: Hi.\n\n"

    turns = parse_transcript_turns(raw)

    assert turns == [("Alice", 5, "Hi.")]


def test_parse_transcript_turns_empty_input_returns_empty_list() -> None:
    assert parse_transcript_turns("") == []


def test_build_meeting_from_transcript_infers_end_ts_from_next_turn() -> None:
    raw = "[00:00:00] Alice: First.\n[00:00:30] Bob: Second.\n[00:01:00] Alice: Third.\n"

    meeting = build_meeting_from_transcript(
        title="Test Meeting",
        meeting_date=date(2026, 1, 1),
        participants=["Alice", "Bob"],
        source_filename="test.txt",
        raw_text=raw,
    )

    assert [chunk.chunk_index for chunk in meeting.chunks] == [0, 1, 2]
    assert meeting.chunks[0].end_ts == 30
    assert meeting.chunks[1].end_ts == 60
    # Last turn has no following turn, so its end_ts falls back to its own start_ts.
    assert meeting.chunks[2].end_ts == meeting.chunks[2].start_ts == 60


def test_build_meeting_from_transcript_leaves_embedding_unset() -> None:
    meeting = build_meeting_from_transcript(
        title="Test Meeting",
        meeting_date=date(2026, 1, 1),
        participants=["Alice"],
        source_filename="test.txt",
        raw_text="[00:00:00] Alice: Hi.\n",
    )

    assert meeting.chunks[0].embedding is None


def test_meeting_metadata_from_filename_parses_date_and_titlecases_slug() -> None:
    title, meeting_date = meeting_metadata_from_filename(
        Path("2026-02-19_leadership-sync-roadmap-prioritization.txt")
    )

    assert title == "Leadership Sync Roadmap Prioritization"
    assert meeting_date == date(2026, 2, 19)


def test_meeting_metadata_from_filename_rejects_unexpected_pattern() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        meeting_metadata_from_filename(Path("not-a-dated-filename.txt"))


def test_load_meeting_from_file_derives_participants_from_speakers(tmp_path: Path) -> None:
    transcript = tmp_path / "2026-03-01_quick-sync.txt"
    transcript.write_text("[00:00:00] Bob: Hi.\n[00:00:10] Alice: Hi back.\n")

    meeting = load_meeting_from_file(transcript)

    assert meeting.title == "Quick Sync"
    assert meeting.date == date(2026, 3, 1)
    assert meeting.participants == ["Alice", "Bob"]  # sorted, not transcript order
    assert meeting.source_filename == "2026-03-01_quick-sync.txt"
    assert len(meeting.chunks) == 2
