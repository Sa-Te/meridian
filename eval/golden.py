"""Golden dataset loading and expected-chunk resolution. See docs/adr/0009.

A golden question names its expected supporting evidence as an exact quoted
substring from the transcript, scoped to one meeting by filename -- not a
hardcoded chunk_index. Chunk ids are assigned at ingest time (random UUIDs)
and chunking merges consecutive same-speaker turns (see
app/services/chunking.py), so a hand-computed index would be both unstable
across re-ingestion and fragile against chunking changes. Matching on quoted
text is stable against both: whichever chunk the quote ends up inside of,
found fresh at eval time, is the right answer.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

Category = Literal["direct_fact", "decision", "action_item", "out_of_scope"]

DEFAULT_GOLDEN_DATASET_PATH = (
    Path(__file__).resolve().parent / "golden_dataset" / "golden_questions.json"
)


@dataclass(frozen=True)
class GoldenQuestion:
    id: str
    category: Category
    question: str
    expected_answer: str
    source_meeting_filename: str | None
    expected_supporting_quotes: list[str]


class GoldenDatasetError(ValueError):
    """Raised when a golden dataset entry can't be resolved against the
    actually-ingested transcript -- a quote that no longer appears in any
    chunk, or that ambiguously appears in more than one. Either means the
    dataset is stale (the transcript changed) and needs fixing, not a value
    to silently tolerate and mis-score around.
    """


def load_golden_questions(path: Path = DEFAULT_GOLDEN_DATASET_PATH) -> list[GoldenQuestion]:
    raw = json.loads(path.read_text())
    return [
        GoldenQuestion(
            id=entry["id"],
            category=entry["category"],
            question=entry["question"],
            expected_answer=entry["expected_answer"],
            source_meeting_filename=entry["source_meeting_filename"],
            expected_supporting_quotes=entry["expected_supporting_quotes"],
        )
        for entry in raw
    ]


class _ChunkLike(Protocol):
    """The subset of app.models.orm.Chunk's fields this module needs, as a
    structural protocol rather than a real dependency on the ORM class --
    unit tests can supply any plain object with these two attributes
    without a database, and app.models.orm.Chunk satisfies it as-is.
    """

    id: UUID
    text: str


def resolve_expected_chunk_ids(question: GoldenQuestion, chunks: Sequence[_ChunkLike]) -> set[UUID]:
    """Resolve a golden question's expected_supporting_quotes to chunk ids,
    by finding the chunk(s) among `chunks` whose text contains each quote.

    Returns an empty set for an out-of-scope question (no expected chunk by
    design). Raises GoldenDatasetError if any quote matches zero or more
    than one chunk -- an ambiguous or stale dataset entry, not a value to
    guess through.
    """
    if not question.expected_supporting_quotes:
        return set()

    expected_ids: set[UUID] = set()
    for quote in question.expected_supporting_quotes:
        matches = [chunk.id for chunk in chunks if quote in chunk.text]
        if len(matches) != 1:
            raise GoldenDatasetError(
                f"Golden question '{question.id}': quote {quote!r} matched "
                f"{len(matches)} chunks in '{question.source_meeting_filename}' "
                "(expected exactly 1). The golden dataset is stale against the "
                "current transcript/chunking -- fix the quote, not this check."
            )
        expected_ids.add(matches[0])
    return expected_ids
