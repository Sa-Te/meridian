from google import genai
from google.genai import types as genai_types

from app.providers.llm.base import LLMMessage, LLMProvider, LLMResponse

DEFAULT_MODEL = "gemini-3.1-flash-lite"

_ROLE_MAP: dict[str, str] = {"user": "user", "assistant": "model"}


class GeminiLLMProvider(LLMProvider):
    """LLMProvider backed by the Gemini API.

    The active default (ADR-0013) -- requires only GEMINI_API_KEY.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        contents = [
            genai_types.Content(
                role=_ROLE_MAP[message.role],
                parts=[genai_types.Part(text=message.content)],
            )
            for message in messages
        ]
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        usage = response.usage_metadata
        return LLMResponse(
            text=response.text or "",
            model=self._model,
            input_tokens=usage.prompt_token_count or 0 if usage else 0,
            output_tokens=usage.candidates_token_count or 0 if usage else 0,
        )
