import re
from dataclasses import dataclass, field

_TURN_PATTERN = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]\s*([^:]+):\s*(.*)$")
_BRACKET_PREFIX_PATTERN = re.compile(r"^\[.*?\]")


class TranscriptParseError(ValueError):
    """Raised when a transcript line can't be parsed and isn't a valid
    continuation of the current turn either. See parse_transcript for
    exactly which formats are (and aren't) supported.
    """


@dataclass(frozen=True)
class SpeakerTurn:
    """One speaker turn, with real start/end timestamps in elapsed seconds
    from the start of the meeting. end_ts is the next turn's start_ts, or
    equal to start_ts for the transcript's final turn, since no true end
    marker exists in this format.
    """

    speaker: str
    start_ts: int
    end_ts: int
    text: str


@dataclass
class _RawTurn:
    speaker: str
    start_ts: int
    text_lines: list[str] = field(default_factory=list)


def _seconds(hours: str, minutes: str, seconds: str) -> int:
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)


def parse_transcript(raw_text: str) -> list[SpeakerTurn]:
    """Parse speaker-labelled, timestamped plain text into ordered turns.

    Supported format, one turn per line, optionally continued on following
    unmarked lines:

        [HH:MM:SS] Speaker: text
        continuation of the same turn, no leading timestamp

    Rules:
    - A line matching "[HH:MM:SS] Speaker: text" always starts a new turn,
      even if the speaker is the same as the previous turn's -- two turns
      from the same speaker in a row are two turns, not one merged turn.
      (Merging same-speaker turns into a single chunk is chunking's job,
      not parsing's -- see app/services/chunking.py.)
    - A non-matching, non-blank line is treated as a continuation of the
      turn currently being built, and is appended to it with a single
      space -- this is how a turn is allowed to span multiple lines.
    - Blank lines are always ignored.

    Deliberately NOT supported, and raised as TranscriptParseError rather
    than silently dropped or misparsed:
    - A non-blank line before any turn has been recognized yet (there is no
      "current turn" for it to continue), e.g. a transcript that opens with
      plain prose instead of a "[HH:MM:SS] Speaker:" line.
    - A line that opens with a bracketed prefix (looks like an attempted
      "[HH:MM:SS]" header) but doesn't fully match the expected pattern --
      e.g. a malformed timestamp, or a missing "Speaker:" segment. Treating
      this as a plain continuation line would silently absorb what was
      probably meant to be a new turn into the previous turn's text.
    """
    raw_turns: list[_RawTurn] = []

    for line_number, source_line in enumerate(raw_text.splitlines(), start=1):
        line = source_line.strip()
        if not line:
            continue

        match = _TURN_PATTERN.match(line)
        if match is not None:
            hours, minutes, seconds, speaker, text = match.groups()
            raw_turns.append(
                _RawTurn(
                    speaker=speaker.strip(),
                    start_ts=_seconds(hours, minutes, seconds),
                    text_lines=[text.strip()],
                )
            )
            continue

        if _BRACKET_PREFIX_PATTERN.match(line) is not None:
            raise TranscriptParseError(
                f"Line {line_number} looks like a timestamped turn header but "
                f"doesn't match the expected '[HH:MM:SS] Speaker: text' format: "
                f"{line!r}"
            )

        if not raw_turns:
            raise TranscriptParseError(
                f"Line {line_number} appears before any recognized "
                f"'[HH:MM:SS] Speaker: text' turn header: {line!r}"
            )

        raw_turns[-1].text_lines.append(line)

    turns: list[SpeakerTurn] = []
    for index, raw_turn in enumerate(raw_turns):
        end_ts = raw_turns[index + 1].start_ts if index + 1 < len(raw_turns) else raw_turn.start_ts
        turns.append(
            SpeakerTurn(
                speaker=raw_turn.speaker,
                start_ts=raw_turn.start_ts,
                end_ts=end_ts,
                text=" ".join(raw_turn.text_lines),
            )
        )
    return turns
