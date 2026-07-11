from abc import ABC, abstractmethod
from typing import Literal, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


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

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: type[SchemaT],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> SchemaT:
        """Generate a completion constrained to response_model's schema via
        the vendor's native structured-output mechanism, returning a
        validated instance of response_model directly -- no manual JSON
        parsing at the call site. See docs/adr/0008 for why extraction uses
        this instead of the plain-JSON-prompt pattern from ADR-0007.
        """
        raise NotImplementedError
