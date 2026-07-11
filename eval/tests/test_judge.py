import asyncio
import uuid

from app.models.orm import Chunk
from app.providers.llm.base import LLMMessage, LLMProvider, LLMResponse, SchemaT
from eval.judge import JudgeVerdict, build_judge_prompt, judge_answer


class _StubLLMProvider(LLMProvider):
    """Records the structured-output call it receives and returns a fixed
    verdict -- eval/'s own test double, not app/tests/fakes.py's
    FakeLLMProvider. The two test suites are independently run (see
    docs/adr/0009), so this stays a small, local duplicate rather than a
    cross-package import.
    """

    def __init__(self, verdict: JudgeVerdict) -> None:
        self._verdict = verdict
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    async def generate(
        self, messages: list[LLMMessage], *, system: str | None = None, **_: object
    ) -> LLMResponse:
        raise AssertionError("judge_answer should call generate_structured, not generate")

    async def generate_structured(
        self, prompt: str, response_model: type[SchemaT], *, system: str | None = None, **_: object
    ) -> SchemaT:
        self.last_prompt = prompt
        self.last_system = system
        assert isinstance(self._verdict, response_model)
        return self._verdict


def _make_chunk(chunk_id: uuid.UUID, text: str) -> Chunk:
    return Chunk(
        id=chunk_id, text=text, speaker="Dr. Vasquez", start_ts=42, end_ts=42, chunk_index=0
    )


def test_build_judge_prompt_marks_cited_and_uncited_excerpts() -> None:
    cited_id, uncited_id = uuid.uuid4(), uuid.uuid4()
    chunks = [
        _make_chunk(cited_id, "The cited excerpt text."),
        _make_chunk(uncited_id, "Unused text."),
    ]

    prompt = build_judge_prompt(
        question="What was decided?",
        answer="They decided X.",
        retrieved_chunks=chunks,
        cited_chunk_ids={cited_id},
    )

    assert "What was decided?" in prompt
    assert "They decided X." in prompt
    assert "[CITED]" in prompt
    assert "[UNCITED]" in prompt
    cited_line = next(line for line in prompt.splitlines() if "The cited excerpt text." in line)
    assert cited_line.startswith("[CITED]")
    uncited_line = next(line for line in prompt.splitlines() if "Unused text." in line)
    assert uncited_line.startswith("[UNCITED]")


def test_build_judge_prompt_handles_no_retrieved_chunks() -> None:
    prompt = build_judge_prompt(
        question="What is the capital of France?",
        answer="I could not find a well-supported answer.",
        retrieved_chunks=[],
        cited_chunk_ids=set(),
    )

    assert "No excerpts were retrieved" in prompt


def test_judge_answer_calls_generate_structured_with_the_judge_prompt_and_system() -> None:
    verdict = JudgeVerdict(
        faithfulness=5,
        faithfulness_reasoning="Fully grounded.",
        relevance=5,
        relevance_reasoning="Directly answers the question.",
    )
    provider = _StubLLMProvider(verdict)
    chunk_id = uuid.uuid4()
    chunks = [_make_chunk(chunk_id, "Some excerpt.")]

    result = asyncio.run(
        judge_answer(
            question="What was decided?",
            answer="They decided X.",
            retrieved_chunks=chunks,
            cited_chunk_ids={chunk_id},
            llm_provider=provider,
        )
    )

    assert result == verdict
    assert provider.last_prompt is not None
    assert "What was decided?" in provider.last_prompt
    assert provider.last_system is not None
    assert "independent evaluator" in provider.last_system
