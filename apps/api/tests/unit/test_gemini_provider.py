from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.providers.llm.base import LLMMessage
from app.providers.llm.gemini_provider import GeminiLLMProvider


def _fake_response(
    text: str = "hello from gemini",
    prompt_tokens: int = 12,
    candidate_tokens: int = 4,
) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt_tokens,
            candidates_token_count=candidate_tokens,
        ),
    )


def _provider() -> GeminiLLMProvider:
    return GeminiLLMProvider(api_key="fake-key", model="gemini-3.1-flash-lite")


async def test_generate_maps_roles_and_returns_response() -> None:
    provider = _provider()
    provider._client.aio.models.generate_content = AsyncMock(return_value=_fake_response())

    result = await provider.generate(
        [LLMMessage(role="user", content="hi"), LLMMessage(role="assistant", content="hello")]
    )

    call = provider._client.aio.models.generate_content.call_args
    contents = call.kwargs["contents"]
    assert [c.role for c in contents] == ["user", "model"]
    assert [c.parts[0].text for c in contents] == ["hi", "hello"]
    assert call.kwargs["model"] == "gemini-3.1-flash-lite"

    assert result.text == "hello from gemini"
    assert result.model == "gemini-3.1-flash-lite"
    assert result.input_tokens == 12
    assert result.output_tokens == 4


async def test_generate_passes_system_and_generation_config() -> None:
    provider = _provider()
    provider._client.aio.models.generate_content = AsyncMock(return_value=_fake_response())

    await provider.generate(
        [LLMMessage(role="user", content="hi")],
        system="be concise",
        max_tokens=256,
        temperature=0.7,
    )

    config = provider._client.aio.models.generate_content.call_args.kwargs["config"]
    assert config.system_instruction == "be concise"
    assert config.max_output_tokens == 256
    assert config.temperature == 0.7


async def test_generate_defaults_tokens_to_zero_without_usage_metadata() -> None:
    provider = _provider()
    response = SimpleNamespace(text="ok", usage_metadata=None)
    provider._client.aio.models.generate_content = AsyncMock(return_value=response)

    result = await provider.generate([LLMMessage(role="user", content="hi")])

    assert result.input_tokens == 0
    assert result.output_tokens == 0


async def test_generate_returns_empty_string_for_no_text() -> None:
    provider = _provider()
    response = _fake_response(text=None)  # type: ignore[arg-type]
    provider._client.aio.models.generate_content = AsyncMock(return_value=response)

    result = await provider.generate([LLMMessage(role="user", content="hi")])

    assert result.text == ""
