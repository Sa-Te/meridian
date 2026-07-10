from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class LLMMessage(BaseModel):
    """A single turn in a conversation sent to an LLMProvider."""

    role: Literal["user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    """The result of an LLMProvider.generate call."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMProvider(ABC):
    """Vendor-agnostic text generation interface (ADR-0002, ADR-0003).

    Concrete implementations (Gemini, Anthropic) are selected at runtime via
    LLM_PROVIDER -- see factory.py and ADR-0013.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Generate a single completion for the given conversation."""
        raise NotImplementedError
