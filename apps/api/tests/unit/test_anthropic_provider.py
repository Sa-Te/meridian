from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.providers.llm.anthropic_provider import AnthropicLLMProvider
from app.providers.llm.base import LLMMessage


def _fake_block(text: str, block_type: str = "text") -> SimpleNamespace:
    return SimpleNamespace(type=block_type, text=text)


def _fake_message(
    blocks: list[SimpleNamespace],
    model: str = "claude-sonnet-5",
    input_tokens: int = 10,
    output_tokens: int = 6,
) -> SimpleNamespace:
    return SimpleNamespace(
        content=blocks,
        model=model,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _provider() -> AnthropicLLMProvider:
    return AnthropicLLMProvider(api_key="fake-key", model="claude-sonnet-5")


async def test_generate_maps_messages_and_returns_response() -> None:
    provider = _provider()
    provider._client.messages.create = AsyncMock(
        return_value=_fake_message([_fake_block("hello from claude")])
    )

    result = await provider.generate(
        [LLMMessage(role="user", content="hi"), LLMMessage(role="assistant", content="hello")]
    )

    call_kwargs = provider._client.messages.create.call_args.kwargs
    assert call_kwargs["messages"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert call_kwargs["model"] == "claude-sonnet-5"
    assert "system" not in call_kwargs

    assert result.text == "hello from claude"
    assert result.model == "claude-sonnet-5"
    assert result.input_tokens == 10
    assert result.output_tokens == 6


async def test_generate_includes_system_when_provided() -> None:
    provider = _provider()
    provider._client.messages.create = AsyncMock(return_value=_fake_message([_fake_block("ok")]))

    await provider.generate([LLMMessage(role="user", content="hi")], system="be concise")

    call_kwargs = provider._client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "be concise"


async def test_generate_joins_multiple_text_blocks_and_skips_non_text() -> None:
    provider = _provider()
    blocks = [
        _fake_block("a"),
        _fake_block("ignored", block_type="tool_use"),
        _fake_block("b"),
    ]
    provider._client.messages.create = AsyncMock(return_value=_fake_message(blocks))

    result = await provider.generate([LLMMessage(role="user", content="hi")])

    assert result.text == "ab"
