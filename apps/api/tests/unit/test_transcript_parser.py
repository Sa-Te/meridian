import pytest

from app.services.transcript_parser import SpeakerTurn, TranscriptParseError, parse_transcript


def test_parses_basic_single_line_turns() -> None:
    raw = "[00:00:05] Alice: Hello there.\n[00:01:10] Bob: Hi Alice.\n"

    turns = parse_transcript(raw)

    assert turns == [
        SpeakerTurn(speaker="Alice", start_ts=5, end_ts=70, text="Hello there."),
        SpeakerTurn(speaker="Bob", start_ts=70, end_ts=70, text="Hi Alice."),
    ]


def test_turn_spanning_multiple_lines_is_joined_with_a_space() -> None:
    raw = (
        "[00:00:05] Alice: Hello there,\nstill talking,\non a third line.\n[00:00:20] Bob: Okay.\n"
    )

    turns = parse_transcript(raw)

    assert turns[0].text == "Hello there, still talking, on a third line."
    assert turns[1].text == "Okay."


def test_consecutive_turns_from_the_same_speaker_stay_separate_turns() -> None:
    raw = "[00:00:00] Alice: First thought.\n[00:00:12] Alice: Second, separate thought.\n"

    turns = parse_transcript(raw)

    assert len(turns) == 2
    assert turns[0].speaker == turns[1].speaker == "Alice"
    assert turns[0].text == "First thought."
    assert turns[1].text == "Second, separate thought."
    assert turns[0].start_ts == 0
    assert turns[1].start_ts == 12


def test_last_turn_end_ts_falls_back_to_its_own_start_ts() -> None:
    raw = "[00:00:00] Alice: Only turn.\n"

    turns = parse_transcript(raw)

    assert turns[0].start_ts == turns[0].end_ts == 0


def test_blank_lines_are_ignored() -> None:
    raw = "\n   \n[00:00:05] Alice: Hi.\n\n\n[00:00:10] Bob: Hey.\n\n"

    turns = parse_transcript(raw)

    assert [turn.speaker for turn in turns] == ["Alice", "Bob"]


def test_empty_input_returns_no_turns() -> None:
    assert parse_transcript("") == []


def test_line_with_no_timestamp_before_any_turn_raises() -> None:
    raw = "Some cold-open line with no timestamp at all.\n[00:00:05] Alice: Hi.\n"

    with pytest.raises(TranscriptParseError, match="before any recognized"):
        parse_transcript(raw)


def test_malformed_timestamp_line_raises_instead_of_being_absorbed() -> None:
    raw = "[00:0x:12] Alice: This looks like a header but isn't one.\n"

    with pytest.raises(TranscriptParseError, match="doesn't match the expected"):
        parse_transcript(raw)


def test_malformed_line_mid_transcript_raises_and_does_not_corrupt_prior_turn() -> None:
    raw = "[00:00:00] Alice: A real turn.\n[00:03] Alice: Missing the seconds field.\n"

    with pytest.raises(TranscriptParseError, match="doesn't match the expected"):
        parse_transcript(raw)
