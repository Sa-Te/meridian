"""Aligns transcription segments against diarization segments to produce
genuinely speaker-labelled, timestamped turns -- the audio-ingestion
equivalent of app/services/transcript_parser.py's parse_transcript, which
this feeds directly into app/services/chunking.py unchanged. See
docs/adr/0012 for why each policy below was chosen and what it trades off.
"""

from app.providers.diarization.base import DiarizationSegment
from app.providers.transcription.base import TranscriptionSegment
from app.services.transcript_parser import SpeakerTurn

UNKNOWN_SPEAKER_LABEL = "Unknown Speaker"

# See docs/adr/0012 for the reasoning behind each default.
DEFAULT_MIN_SEGMENT_DURATION_SECONDS = 0.5
DEFAULT_MIN_OVERLAP_FRACTION = 0.5
DEFAULT_OVERLAP_CONTEST_MARGIN = 0.2
DEFAULT_OVERLAP_CONTEST_FLOOR = 0.3


def _overlap_duration(
    segment_start: float, segment_end: float, other_start: float, other_end: float
) -> float:
    return max(0.0, min(segment_end, other_end) - max(segment_start, other_start))


def _resolve_speaker(
    segment: TranscriptionSegment,
    diarization_segments: list[DiarizationSegment],
    *,
    min_segment_duration_seconds: float,
    min_overlap_fraction: float,
    overlap_contest_margin: float,
    overlap_contest_floor: float,
) -> str | None:
    """Returns the raw diarization speaker_label this transcription segment
    should be attributed to, or None if it should be labelled
    UNKNOWN_SPEAKER_LABEL instead of guessed. Four rules, checked in order:

    1. Short utterance: a segment shorter than min_segment_duration_seconds
       carries too little signal for confident attribution regardless of
       what diarization says -- a one-word "Okay." is exactly the case the
       ROADMAP names explicitly.
    2. No overlap: no diarization segment covers any part of this one at
       all (a gap in the diarization pass, or audio diarization treated as
       non-speech).
    3. No clear majority: even the best-covering speaker accounts for less
       than min_overlap_fraction of the segment's duration -- attribution
       would be a guess, not a finding.
    4. Contested overlap: two speakers each cover a substantial, similar
       share of the segment (the runner-up is within overlap_contest_margin
       of the winner, and itself clears overlap_contest_floor) -- this is
       what genuine overlapping/cross-talk speech looks like in the
       overlap-duration data, and picking either speaker over the other
       would be a coin flip dressed up as a finding.
    """
    duration = segment.end_ts - segment.start_ts
    if duration < min_segment_duration_seconds:
        return None

    overlap_by_speaker: dict[str, float] = {}
    for diarized in diarization_segments:
        overlap = _overlap_duration(
            segment.start_ts, segment.end_ts, diarized.start_ts, diarized.end_ts
        )
        if overlap > 0:
            overlap_by_speaker[diarized.speaker_label] = (
                overlap_by_speaker.get(diarized.speaker_label, 0.0) + overlap
            )

    if not overlap_by_speaker:
        return None

    ranked = sorted(overlap_by_speaker.items(), key=lambda item: item[1], reverse=True)
    best_speaker, best_overlap = ranked[0]
    best_fraction = best_overlap / duration

    if best_fraction < min_overlap_fraction:
        return None

    if len(ranked) > 1:
        second_fraction = ranked[1][1] / duration
        contested = (
            best_fraction - second_fraction < overlap_contest_margin
            and second_fraction >= overlap_contest_floor
        )
        if contested:
            return None

    return best_speaker


def align_transcript_and_diarization(
    transcription_segments: list[TranscriptionSegment],
    diarization_segments: list[DiarizationSegment],
    *,
    min_segment_duration_seconds: float = DEFAULT_MIN_SEGMENT_DURATION_SECONDS,
    min_overlap_fraction: float = DEFAULT_MIN_OVERLAP_FRACTION,
    overlap_contest_margin: float = DEFAULT_OVERLAP_CONTEST_MARGIN,
    overlap_contest_floor: float = DEFAULT_OVERLAP_CONTEST_FLOOR,
) -> list[SpeakerTurn]:
    """Attribute each transcription segment to a speaker, producing
    SpeakerTurn objects ready for app/services/chunking.py's chunk_turns
    (unchanged) -- exactly the shape parse_transcript produces for a
    hand-typed transcript.

    Raw diarization labels (e.g. "SPEAKER_00") are remapped to stable,
    human-readable "Speaker N" labels in first-appearance order; a segment
    that fails every attribution rule gets UNKNOWN_SPEAKER_LABEL instead of
    a guessed name. Neither more nor fewer distinct labels than diarization
    actually produced are invented or merged here -- if the diarization
    pass over- or under-counts real speakers, that shows up honestly as
    more or fewer "Speaker N" labels, not silently corrected (see
    docs/adr/0012).
    """
    stable_labels: dict[str, str] = {}
    turns: list[SpeakerTurn] = []

    for segment in transcription_segments:
        text = segment.text.strip()
        if not text:
            continue

        raw_speaker = _resolve_speaker(
            segment,
            diarization_segments,
            min_segment_duration_seconds=min_segment_duration_seconds,
            min_overlap_fraction=min_overlap_fraction,
            overlap_contest_margin=overlap_contest_margin,
            overlap_contest_floor=overlap_contest_floor,
        )
        if raw_speaker is None:
            speaker_label = UNKNOWN_SPEAKER_LABEL
        else:
            if raw_speaker not in stable_labels:
                stable_labels[raw_speaker] = f"Speaker {len(stable_labels) + 1}"
            speaker_label = stable_labels[raw_speaker]

        turns.append(
            SpeakerTurn(
                speaker=speaker_label,
                start_ts=round(segment.start_ts),
                end_ts=round(segment.end_ts),
                text=text,
            )
        )

    return turns
