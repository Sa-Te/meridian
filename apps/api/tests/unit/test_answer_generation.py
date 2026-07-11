import json
import uuid

from app.models.orm import Chunk
from app.services.answer_generation import UNSUPPORTED_ANSWER, Citation, generate_answer
from tests.fakes import FakeLLMProvider


def _chunk(chunk_id: uuid.UUID, text: str = "some transcript text") -> Chunk:
    return Chunk(
        id=chunk_id,
        meeting_id=uuid.uuid4(),
        speaker="Alice",
        start_ts=12,
        end_ts=20,
        text=text,
        chunk_index=0,
    )


def _valid_response(chunk_id: uuid.UUID, answer: str = "The answer is X.") -> str:
    return json.dumps(
        {"supported": True, "answer": answer, "citations": [{"chunk_id": str(chunk_id)}]}
    )


async def test_no_retrieved_chunks_returns_unsupported_without_calling_the_llm() -> None:
    llm = FakeLLMProvider(responses=[])

    result = await generate_answer(question="Anything?", retrieved_chunks=[], llm_provider=llm)

    assert result.supported is False
    assert result.answer == UNSUPPORTED_ANSWER
    assert result.citations == []
    assert llm.calls == []


async def test_valid_first_response_is_accepted_without_a_retry() -> None:
    chunk_id = uuid.uuid4()
    llm = FakeLLMProvider(responses=[_valid_response(chunk_id, "Five to seven workouts.")])

    result = await generate_answer(
        question="How many workouts?", retrieved_chunks=[_chunk(chunk_id)], llm_provider=llm
    )

    assert result.supported is True
    assert result.answer == "Five to seven workouts."
    assert result.citations == [Citation(chunk_id=chunk_id)]
    assert len(llm.calls) == 1


async def test_model_reported_unsupported_is_honored_without_a_retry() -> None:
    chunk_id = uuid.uuid4()
    honest_refusal = json.dumps(
        {"supported": False, "answer": "The excerpts don't cover this.", "citations": []}
    )
    llm = FakeLLMProvider(responses=[honest_refusal])

    result = await generate_answer(
        question="Unrelated question", retrieved_chunks=[_chunk(chunk_id)], llm_provider=llm
    )

    assert result.supported is False
    assert result.answer == "The excerpts don't cover this."
    assert result.citations == []
    assert len(llm.calls) == 1


async def test_malformed_json_triggers_one_retry_then_succeeds() -> None:
    chunk_id = uuid.uuid4()
    llm = FakeLLMProvider(responses=["not json at all", _valid_response(chunk_id)])

    result = await generate_answer(
        question="Q", retrieved_chunks=[_chunk(chunk_id)], llm_provider=llm
    )

    assert result.supported is True
    assert len(llm.calls) == 2


async def test_citation_to_an_unretrieved_chunk_triggers_a_retry_then_succeeds() -> None:
    retrieved_id = uuid.uuid4()
    hallucinated_id = uuid.uuid4()
    bad_response = _valid_response(hallucinated_id)
    good_response = _valid_response(retrieved_id)
    llm = FakeLLMProvider(responses=[bad_response, good_response])

    result = await generate_answer(
        question="Q", retrieved_chunks=[_chunk(retrieved_id)], llm_provider=llm
    )

    assert result.supported is True
    assert result.citations[0].chunk_id == retrieved_id
    assert len(llm.calls) == 2


async def test_supported_true_with_no_citations_is_a_guardrail_failure() -> None:
    chunk_id = uuid.uuid4()
    empty_citations = json.dumps({"supported": True, "answer": "X", "citations": []})
    llm = FakeLLMProvider(responses=[empty_citations, _valid_response(chunk_id)])

    result = await generate_answer(
        question="Q", retrieved_chunks=[_chunk(chunk_id)], llm_provider=llm
    )

    assert result.supported is True
    assert len(llm.calls) == 2


async def test_two_failed_attempts_fall_back_to_unsupported() -> None:
    llm = FakeLLMProvider(responses=["garbage", "still garbage"])

    result = await generate_answer(
        question="Q", retrieved_chunks=[_chunk(uuid.uuid4())], llm_provider=llm
    )

    assert result.supported is False
    assert result.answer == UNSUPPORTED_ANSWER
    assert result.citations == []
    assert len(llm.calls) == 2


async def test_json_wrapped_in_a_markdown_code_fence_is_still_parsed() -> None:
    chunk_id = uuid.uuid4()
    fenced = f"```json\n{_valid_response(chunk_id)}\n```"
    llm = FakeLLMProvider(responses=[fenced])

    result = await generate_answer(
        question="Q", retrieved_chunks=[_chunk(chunk_id)], llm_provider=llm
    )

    assert result.supported is True
    assert len(llm.calls) == 1


async def test_duplicate_citations_are_deduplicated_preserving_order() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    response = json.dumps(
        {
            "supported": True,
            "answer": "X",
            "citations": [
                {"chunk_id": str(first_id)},
                {"chunk_id": str(second_id)},
                {"chunk_id": str(first_id)},
            ],
        }
    )
    llm = FakeLLMProvider(responses=[response])

    result = await generate_answer(
        question="Q",
        retrieved_chunks=[_chunk(first_id), _chunk(second_id)],
        llm_provider=llm,
    )

    assert [citation.chunk_id for citation in result.citations] == [first_id, second_id]
