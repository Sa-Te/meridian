import uuid
from datetime import date

from app.models.orm import Chunk
from app.services.extraction import (
    ExtractedActionItem,
    ExtractedDecision,
    _LLMActionItem,
    _LLMDecision,
    _LLMExtractionPayload,
    extract_records,
    to_orm_action_items,
    to_orm_decisions,
)
from tests.fakes import FakeLLMProvider


def _chunk(chunk_index: int = 0) -> Chunk:
    return Chunk(
        id=uuid.uuid4(),
        meeting_id=uuid.uuid4(),
        speaker="Dhruvisha",
        start_ts=10,
        end_ts=20,
        text="some transcript text",
        chunk_index=chunk_index,
    )


async def test_no_chunks_returns_empty_result_without_calling_the_llm() -> None:
    llm = FakeLLMProvider(structured_responses=[])

    result = await extract_records(meeting_chunks=[], llm_provider=llm, confidence_threshold=0.5)

    assert result.decisions == []
    assert result.action_items == []
    assert llm.structured_calls == []


async def test_valid_decision_and_action_item_are_kept() -> None:
    chunk = _chunk()
    payload = _LLMExtractionPayload(
        decisions=[
            _LLMDecision(
                text="We will ship the new alert threshold.",
                source_chunk_id=chunk.id,
                confidence=0.9,
            )
        ],
        action_items=[
            _LLMActionItem(
                text="Send the source for the 40% figure.",
                owner="Dr. Vasquez",
                due_date=date(2026, 2, 1),
                source_chunk_id=chunk.id,
                confidence=0.85,
            )
        ],
    )
    llm = FakeLLMProvider(structured_responses=[payload])

    result = await extract_records(
        meeting_chunks=[chunk], llm_provider=llm, confidence_threshold=0.5
    )

    assert result.decisions == [
        ExtractedDecision(
            text="We will ship the new alert threshold.", source_chunk_id=chunk.id, confidence=0.9
        )
    ]
    assert result.action_items == [
        ExtractedActionItem(
            text="Send the source for the 40% figure.",
            owner="Dr. Vasquez",
            due_date=date(2026, 2, 1),
            source_chunk_id=chunk.id,
            confidence=0.85,
        )
    ]
    assert len(llm.structured_calls) == 1


async def test_low_confidence_item_is_dropped_but_others_are_kept() -> None:
    chunk = _chunk()
    payload = _LLMExtractionPayload(
        decisions=[
            _LLMDecision(text="Confident decision.", source_chunk_id=chunk.id, confidence=0.9),
            _LLMDecision(text="Unsure decision.", source_chunk_id=chunk.id, confidence=0.2),
        ],
        action_items=[],
    )
    llm = FakeLLMProvider(structured_responses=[payload])

    result = await extract_records(
        meeting_chunks=[chunk], llm_provider=llm, confidence_threshold=0.5
    )

    assert [d.text for d in result.decisions] == ["Confident decision."]


async def test_hallucinated_source_chunk_id_is_dropped_but_others_are_kept() -> None:
    chunk = _chunk()
    hallucinated_id = uuid.uuid4()
    payload = _LLMExtractionPayload(
        decisions=[],
        action_items=[
            _LLMActionItem(text="Real item.", source_chunk_id=chunk.id, confidence=0.9),
            _LLMActionItem(
                text="Hallucinated item.", source_chunk_id=hallucinated_id, confidence=0.9
            ),
        ],
    )
    llm = FakeLLMProvider(structured_responses=[payload])

    result = await extract_records(
        meeting_chunks=[chunk], llm_provider=llm, confidence_threshold=0.5
    )

    assert [a.text for a in result.action_items] == ["Real item."]


async def test_failed_first_generation_triggers_one_retry_then_succeeds() -> None:
    chunk = _chunk()
    payload = _LLMExtractionPayload(
        decisions=[_LLMDecision(text="Decision.", source_chunk_id=chunk.id, confidence=0.9)],
        action_items=[],
    )
    llm = FakeLLMProvider(structured_responses=[ValueError("truncated response"), payload])

    result = await extract_records(
        meeting_chunks=[chunk], llm_provider=llm, confidence_threshold=0.5
    )

    assert [d.text for d in result.decisions] == ["Decision."]
    assert len(llm.structured_calls) == 2


async def test_two_failed_generations_fall_back_to_empty_result() -> None:
    chunk = _chunk()
    llm = FakeLLMProvider(structured_responses=[ValueError("bad"), ValueError("still bad")])

    result = await extract_records(
        meeting_chunks=[chunk], llm_provider=llm, confidence_threshold=0.5
    )

    assert result.decisions == []
    assert result.action_items == []
    assert len(llm.structured_calls) == 2


def test_to_orm_decisions_maps_fields() -> None:
    chunk_id = uuid.uuid4()
    decisions = [ExtractedDecision(text="X", source_chunk_id=chunk_id, confidence=0.7)]

    orm_decisions = to_orm_decisions(decisions)

    assert len(orm_decisions) == 1
    assert orm_decisions[0].text == "X"
    assert orm_decisions[0].source_chunk_id == chunk_id
    assert orm_decisions[0].confidence == 0.7


def test_to_orm_action_items_maps_fields_including_owner_and_due_date() -> None:
    chunk_id = uuid.uuid4()
    action_items = [
        ExtractedActionItem(
            text="Y",
            owner="Naomi",
            due_date=date(2026, 3, 1),
            source_chunk_id=chunk_id,
            confidence=0.6,
        )
    ]

    orm_items = to_orm_action_items(action_items)

    assert len(orm_items) == 1
    assert orm_items[0].text == "Y"
    assert orm_items[0].owner == "Naomi"
    assert orm_items[0].due_date == date(2026, 3, 1)
    assert orm_items[0].source_chunk_id == chunk_id
    assert orm_items[0].confidence == 0.6
