from typing import Any

from anthropic import AsyncAnthropic

from app.providers.llm.base import LLMMessage, LLMProvider, LLMResponse

DEFAULT_MODEL = "claude-sonnet-5"


class AnthropicLLMProvider(LLMProvider):
    """LLMProvider backed by the Anthropic Messages API.

    A second working implementation of the interface, kept to demonstrate
    the provider abstraction (ADR-0003). Not the active default -- selected
    via LLM_PROVIDER=anthropic, which requires ANTHROPIC_API_KEY. See
    ADR-0013.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system is not None:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)

        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
