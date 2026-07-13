import asyncio
import contextlib

from pydantic import BaseModel

from app.providers.llm.base import LLMMessage, LLMProvider, LLMResponse, SchemaT
from eval.caching_llm_provider import CachingLLMProvider


class _Verdict(BaseModel):
    score: int


class _CountingLLMProvider(LLMProvider):
    """Records how many times each method was actually invoked, and can be
    made to fail on demand -- the thing CachingLLMProvider wraps."""

    def __init__(self) -> None:
        self.generate_calls = 0
        self.structured_calls = 0
        self.fail_generate_next = False

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        self.generate_calls += 1
        if self.fail_generate_next:
            self.fail_generate_next = False
            raise RuntimeError("transient failure")
        return LLMResponse(
            text=f"response #{self.generate_calls}", model="fake", input_tokens=0, output_tokens=0
        )

    async def generate_structured(
        self, prompt: str, response_model: type[SchemaT], *, system: str | None = None, **_: object
    ) -> SchemaT:
        self.structured_calls += 1
        assert response_model is _Verdict
        return _Verdict(score=self.structured_calls)  # type: ignore[return-value]


def test_generate_reuses_the_response_for_an_identical_call() -> None:
    inner = _CountingLLMProvider()
    provider = CachingLLMProvider(inner)
    messages = [LLMMessage(role="user", content="What was decided?")]

    first = asyncio.run(provider.generate(messages, system="be concise"))
    second = asyncio.run(provider.generate(messages, system="be concise"))

    assert first == second
    assert inner.generate_calls == 1


def test_generate_calls_through_again_for_a_different_prompt() -> None:
    inner = _CountingLLMProvider()
    provider = CachingLLMProvider(inner)

    asyncio.run(provider.generate([LLMMessage(role="user", content="Question A")]))
    asyncio.run(provider.generate([LLMMessage(role="user", content="Question B")]))

    assert inner.generate_calls == 2


def test_generate_calls_through_again_when_system_or_temperature_differs() -> None:
    inner = _CountingLLMProvider()
    provider = CachingLLMProvider(inner)
    messages = [LLMMessage(role="user", content="Same question")]

    asyncio.run(provider.generate(messages, system="prompt A"))
    asyncio.run(provider.generate(messages, system="prompt B"))
    asyncio.run(provider.generate(messages, system="prompt A", temperature=0.5))

    assert inner.generate_calls == 3


def test_generate_structured_reuses_the_response_for_an_identical_call() -> None:
    inner = _CountingLLMProvider()
    provider = CachingLLMProvider(inner)

    first = asyncio.run(provider.generate_structured("judge this", _Verdict, system="judge"))
    second = asyncio.run(provider.generate_structured("judge this", _Verdict, system="judge"))

    assert first == second == _Verdict(score=1)
    assert inner.structured_calls == 1


def test_a_failed_call_is_not_cached_so_a_retry_goes_out_for_real() -> None:
    inner = _CountingLLMProvider()
    inner.fail_generate_next = True
    provider = CachingLLMProvider(inner)
    messages = [LLMMessage(role="user", content="Retried question")]

    with contextlib.suppress(RuntimeError):
        asyncio.run(provider.generate(messages))

    result = asyncio.run(provider.generate(messages))

    assert result.text == "response #2"
    assert inner.generate_calls == 2
