import re
from collections.abc import Callable
from dataclasses import dataclass

from app.services.transcript_parser import SpeakerTurn

# A whitespace-delimited word count, used as a cheap, dependency-free proxy
# for subword token count. See docs/adr/0006 for why this approximation was
# chosen over counting real embedding-model tokens.
TokenCounter = Callable[[str], int]

DEFAULT_MAX_CHUNK_TOKENS = 220

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ChunkData:
    """One chunk ready to become a Chunk row -- speaker, timestamps, and
    text, with no embedding or chunk_index yet (assigned by the ingestion
    service).
    """

    speaker: str
    start_ts: int
    end_ts: int
    text: str


def count_words(text: str) -> int:
    return len(text.split())


def _split_into_sentences(text: str) -> list[str]:
    """Naive sentence splitter: breaks after '.', '!', or '?' followed by
    whitespace. Known, deliberate limitation: abbreviations like "Dr." or
    "e.g." are misread as sentence boundaries. Acceptable here because the
    only consequence is an extra, still-correct chunk boundary -- never
    corrupted or dropped text.
    """
    sentences = [
        sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(text) if sentence.strip()
    ]
    return sentences or [text]


def _split_oversized_turn(
    turn: SpeakerTurn, *, max_tokens: int, count_tokens: TokenCounter
) -> list[ChunkData]:
    """Split a single turn that exceeds max_tokens into multiple chunks
    along sentence boundaries, greedily packing sentences up to the budget.

    All resulting pieces share the parent turn's start_ts/end_ts -- the
    transcript format only carries one timestamp pair per turn, so there is
    no finer-grained timing to assign sub-chunks.

    If a single sentence alone exceeds max_tokens, it is kept whole rather
    than cut mid-sentence -- the sentence boundary is the hard limit on how
    finely this splits, by design (see docs/adr/0006).
    """
    pieces: list[ChunkData] = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in _split_into_sentences(turn.text):
        sentence_tokens = count_tokens(sentence)
        if current_sentences and current_tokens + sentence_tokens > max_tokens:
            pieces.append(
                ChunkData(
                    speaker=turn.speaker,
                    start_ts=turn.start_ts,
                    end_ts=turn.end_ts,
                    text=" ".join(current_sentences),
                )
            )
            current_sentences = []
            current_tokens = 0
        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    if current_sentences:
        pieces.append(
            ChunkData(
                speaker=turn.speaker,
                start_ts=turn.start_ts,
                end_ts=turn.end_ts,
                text=" ".join(current_sentences),
            )
        )
    return pieces


def chunk_turns(
    turns: list[SpeakerTurn],
    *,
    max_tokens: int = DEFAULT_MAX_CHUNK_TOKENS,
    count_tokens: TokenCounter = count_words,
) -> list[ChunkData]:
    """Speaker-turn-aware chunking (see docs/adr/0006):

    - Consecutive turns from the SAME speaker are merged into one chunk, up
      to max_tokens. A chunk never contains more than one speaker.
    - A turn never splits across a chunk boundary unless the turn alone
      exceeds max_tokens, in which case it's split along sentence
      boundaries (see _split_oversized_turn).
    """
    chunks: list[ChunkData] = []
    pending: list[SpeakerTurn] = []
    pending_tokens = 0

    def flush_pending() -> None:
        nonlocal pending, pending_tokens
        if not pending:
            return
        chunks.append(
            ChunkData(
                speaker=pending[0].speaker,
                start_ts=pending[0].start_ts,
                end_ts=pending[-1].end_ts,
                text=" ".join(turn.text for turn in pending),
            )
        )
        pending = []
        pending_tokens = 0

    for turn in turns:
        turn_tokens = count_tokens(turn.text)

        if turn_tokens > max_tokens:
            flush_pending()
            chunks.extend(
                _split_oversized_turn(turn, max_tokens=max_tokens, count_tokens=count_tokens)
            )
            continue

        same_speaker_as_pending = bool(pending) and pending[-1].speaker == turn.speaker
        fits_in_pending_budget = pending_tokens + turn_tokens <= max_tokens

        if pending and not (same_speaker_as_pending and fits_in_pending_budget):
            flush_pending()

        pending.append(turn)
        pending_tokens += turn_tokens

    flush_pending()
    return chunks
