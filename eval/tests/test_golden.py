import uuid

import pytest

from app.models.orm import Chunk
from eval.golden import (
    DEFAULT_GOLDEN_DATASET_PATH,
    GoldenDatasetError,
    GoldenQuestion,
    load_golden_questions,
    resolve_expected_chunk_ids,
)

_VALID_CATEGORIES = {"direct_fact", "decision", "action_item", "out_of_scope"}


def _make_chunk(text: str) -> Chunk:
    return Chunk(id=uuid.uuid4(), text=text, speaker="Someone", start_ts=0, end_ts=0, chunk_index=0)


def test_load_golden_questions_loads_the_real_dataset() -> None:
    questions = load_golden_questions(DEFAULT_GOLDEN_DATASET_PATH)

    assert 15 <= len(questions) <= 20
    assert all(question.category in _VALID_CATEGORIES for question in questions)
    assert len({question.id for question in questions}) == len(questions)

    out_of_scope = [q for q in questions if q.category == "out_of_scope"]
    assert 2 <= len(out_of_scope) <= 3
    assert all(q.source_meeting_filename is None for q in out_of_scope)
    assert all(q.expected_supporting_quotes == [] for q in out_of_scope)

    in_scope = [q for q in questions if q.category != "out_of_scope"]
    assert all(q.source_meeting_filename is not None for q in in_scope)
    assert all(q.expected_supporting_quotes for q in in_scope)


def test_resolve_expected_chunk_ids_returns_empty_set_for_out_of_scope_question() -> None:
    question = GoldenQuestion(
        id="oos-1",
        category="out_of_scope",
        question="What is the capital of France?",
        expected_answer="Not well-supported.",
        source_meeting_filename=None,
        expected_supporting_quotes=[],
    )

    assert resolve_expected_chunk_ids(question, chunks=[]) == set()


def test_resolve_expected_chunk_ids_matches_the_chunk_containing_the_quote() -> None:
    target = _make_chunk("Fifty patients, one Riverside site, starting Q2.")
    other = _make_chunk("Some unrelated turn about something else entirely.")
    question = GoldenQuestion(
        id="df-1",
        category="direct_fact",
        question="How many patients?",
        expected_answer="Fifty.",
        source_meeting_filename="riverside.txt",
        expected_supporting_quotes=["one Riverside site, starting Q2"],
    )

    assert resolve_expected_chunk_ids(question, chunks=[target, other]) == {target.id}


def test_resolve_expected_chunk_ids_supports_multiple_quotes() -> None:
    first = _make_chunk("The wearable connection becomes optional.")
    second = _make_chunk("Sam ships it by Friday.")
    question = GoldenQuestion(
        id="dec-1",
        category="decision",
        question="What was decided?",
        expected_answer="Wearable is optional.",
        source_meeting_filename="onboarding.txt",
        expected_supporting_quotes=["becomes optional", "ships it by Friday"],
    )

    assert resolve_expected_chunk_ids(question, chunks=[first, second]) == {first.id, second.id}


def test_resolve_expected_chunk_ids_raises_when_quote_matches_no_chunk() -> None:
    question = GoldenQuestion(
        id="df-1",
        category="direct_fact",
        question="How many patients?",
        expected_answer="Fifty.",
        source_meeting_filename="riverside.txt",
        expected_supporting_quotes=["a phrase that appears nowhere"],
    )

    with pytest.raises(GoldenDatasetError, match="matched 0 chunks"):
        resolve_expected_chunk_ids(question, chunks=[_make_chunk("Something else entirely.")])


def test_resolve_expected_chunk_ids_raises_when_quote_matches_multiple_chunks() -> None:
    question = GoldenQuestion(
        id="df-1",
        category="direct_fact",
        question="How many patients?",
        expected_answer="Fifty.",
        source_meeting_filename="riverside.txt",
        expected_supporting_quotes=["shared phrase"],
    )
    chunks = [_make_chunk("This has the shared phrase in it."), _make_chunk("shared phrase again")]

    with pytest.raises(GoldenDatasetError, match="matched 2 chunks"):
        resolve_expected_chunk_ids(question, chunks=chunks)
