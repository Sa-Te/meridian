from app.providers.diarization.base import DiarizationSegment
from app.providers.transcription.base import TranscriptionSegment
from app.services.audio_alignment import UNKNOWN_SPEAKER_LABEL, align_transcript_and_diarization


def _trans(start: float, end: float, text: str = "hello") -> TranscriptionSegment:
    return TranscriptionSegment(start_ts=start, end_ts=end, text=text)


def _diar(start: float, end: float, speaker: str) -> DiarizationSegment:
    return DiarizationSegment(start_ts=start, end_ts=end, speaker_label=speaker)


def test_single_segment_fully_covered_by_one_speaker() -> None:
    turns = align_transcript_and_diarization(
        [_trans(0.0, 2.0, "Good morning.")],
        [_diar(0.0, 2.0, "SPEAKER_00")],
    )

    assert len(turns) == 1
    assert turns[0].speaker == "Speaker 1"
    assert turns[0].start_ts == 0
    assert turns[0].end_ts == 2


def test_stable_labels_assigned_in_first_appearance_order_and_reused() -> None:
    turns = align_transcript_and_diarization(
        [
            _trans(0.0, 2.0, "First."),
            _trans(2.0, 4.0, "Second."),
            _trans(4.0, 6.0, "First again."),
        ],
        [
            _diar(0.0, 2.0, "SPEAKER_01"),
            _diar(2.0, 4.0, "SPEAKER_00"),
            _diar(4.0, 6.0, "SPEAKER_01"),
        ],
    )

    # SPEAKER_01 appears first (chronologically) so it becomes "Speaker 1",
    # even though pyannote's own internal label numbering suggests otherwise.
    assert [turn.speaker for turn in turns] == ["Speaker 1", "Speaker 2", "Speaker 1"]


def test_rounds_fractional_timestamps_to_whole_seconds() -> None:
    turns = align_transcript_and_diarization(
        [_trans(0.2, 2.7, "Hello.")],
        [_diar(0.0, 3.0, "SPEAKER_00")],
    )

    assert turns[0].start_ts == 0
    assert turns[0].end_ts == 3


def test_skips_segments_with_empty_or_whitespace_only_text() -> None:
    turns = align_transcript_and_diarization(
        [_trans(0.0, 1.0, "   "), _trans(1.0, 3.0, "Real content.")],
        [_diar(0.0, 3.0, "SPEAKER_00")],
    )

    assert len(turns) == 1
    assert turns[0].text == "Real content."


def test_rule1_short_utterance_is_labelled_unknown_even_with_perfect_overlap() -> None:
    turns = align_transcript_and_diarization(
        [_trans(10.0, 10.3, "Okay.")],  # 0.3s, below the 0.5s default floor
        [_diar(9.0, 12.0, "SPEAKER_00")],
    )

    assert turns[0].speaker == UNKNOWN_SPEAKER_LABEL


def test_rule1_threshold_is_configurable() -> None:
    turns = align_transcript_and_diarization(
        [_trans(10.0, 10.3, "Okay.")],
        [_diar(9.0, 12.0, "SPEAKER_00")],
        min_segment_duration_seconds=0.1,
    )

    assert turns[0].speaker == "Speaker 1"


def test_rule2_no_overlapping_diarization_segment_is_labelled_unknown() -> None:
    turns = align_transcript_and_diarization(
        [_trans(0.0, 2.0, "Hello.")],
        [_diar(5.0, 7.0, "SPEAKER_00")],  # entirely outside the transcription segment
    )

    assert turns[0].speaker == UNKNOWN_SPEAKER_LABEL


def test_rule3_best_speaker_below_majority_threshold_is_labelled_unknown() -> None:
    # A 4s segment where the only overlapping speaker covers just 1s (25%).
    turns = align_transcript_and_diarization(
        [_trans(0.0, 4.0, "Some words.")],
        [_diar(3.0, 4.0, "SPEAKER_00")],
    )

    assert turns[0].speaker == UNKNOWN_SPEAKER_LABEL


def test_rule4_contested_overlap_between_two_similar_speakers_is_unknown() -> None:
    # A 4s segment split almost evenly: SPEAKER_00 covers 2.2s, SPEAKER_01
    # covers 1.8s -- both clear the majority-adjacent floor and are close
    # enough together to be genuine overlapping/cross-talk speech.
    turns = align_transcript_and_diarization(
        [_trans(0.0, 4.0, "Overlapping speech.")],
        [_diar(0.0, 2.2, "SPEAKER_00"), _diar(2.2, 4.0, "SPEAKER_01")],
    )

    assert turns[0].speaker == UNKNOWN_SPEAKER_LABEL


def test_dominant_speaker_with_minor_second_speaker_is_not_contested() -> None:
    # A 4s segment: SPEAKER_00 covers 3.2s (80%), SPEAKER_01 covers 0.8s
    # (20%, below the contest floor) -- a clean majority, not overlap.
    turns = align_transcript_and_diarization(
        [_trans(0.0, 4.0, "Mostly one speaker.")],
        [_diar(0.0, 3.2, "SPEAKER_00"), _diar(3.2, 4.0, "SPEAKER_01")],
    )

    assert turns[0].speaker == "Speaker 1"


def test_two_speakers_above_contest_floor_but_far_apart_is_not_contested() -> None:
    # A 4s segment: SPEAKER_00 covers 3.2s (80%), SPEAKER_01 covers 1.4s of
    # a genuinely overlapping window (35%, above the 0.3 floor) -- but the
    # 45-point margin between them is well past the 20-point contest
    # margin, so this is a dominant speaker with some bleed-over, not a
    # coin flip.
    turns = align_transcript_and_diarization(
        [_trans(0.0, 4.0, "Mostly one speaker with some overlap.")],
        [_diar(0.0, 3.2, "SPEAKER_00"), _diar(2.4, 3.8, "SPEAKER_01")],
    )

    assert turns[0].speaker == "Speaker 1"


def test_overlap_thresholds_are_configurable() -> None:
    # Same contested 50/50 split as the rule-4 test above, but with a
    # margin wide enough to swallow any split -- should now resolve to
    # the (arbitrary but deterministic) higher-overlap speaker.
    turns = align_transcript_and_diarization(
        [_trans(0.0, 4.0, "Overlapping speech.")],
        [_diar(0.0, 2.2, "SPEAKER_00"), _diar(2.2, 4.0, "SPEAKER_01")],
        overlap_contest_margin=0.0,
    )

    assert turns[0].speaker == "Speaker 1"


def test_multiple_diarization_segments_from_the_same_speaker_sum_their_overlap() -> None:
    # SPEAKER_00 speaks twice within one transcription segment's span (a
    # brief diarization gap in the middle) -- total overlap should still
    # dominate over SPEAKER_01's smaller single segment.
    turns = align_transcript_and_diarization(
        [_trans(0.0, 4.0, "One speaker, briefly interrupted by diarization noise.")],
        [
            _diar(0.0, 1.8, "SPEAKER_00"),
            _diar(1.8, 2.0, "SPEAKER_01"),
            _diar(2.0, 4.0, "SPEAKER_00"),
        ],
    )

    assert turns[0].speaker == "Speaker 1"


def test_empty_diarization_segments_labels_everything_unknown() -> None:
    turns = align_transcript_and_diarization(
        [_trans(0.0, 2.0, "Hello."), _trans(2.0, 4.0, "Anyone there?")],
        [],
    )

    assert all(turn.speaker == UNKNOWN_SPEAKER_LABEL for turn in turns)


def test_empty_transcription_segments_returns_no_turns() -> None:
    turns = align_transcript_and_diarization([], [_diar(0.0, 2.0, "SPEAKER_00")])

    assert turns == []
