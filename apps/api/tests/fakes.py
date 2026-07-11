"""Shared test doubles, importable from both tests/unit and tests/integration."""

from app.providers.embedding.base import EmbeddingProvider
from app.providers.llm.base import LLMMessage, LLMProvider, LLMResponse


class FakeEmbeddingProvider(EmbeddingProvider):
    """A deterministic EmbeddingProvider for tests that shouldn't need to
    load a real model or call a real API. Not a real embedding -- just a
    fixed-dimension vector derived from each text's contents, enough to
    exercise the pipeline's plumbing (ordering, dimensionality, storage,
    and cosine-similarity search returning *some* meaningfully varying
    ranking). Each dimension is seeded from a checksum of character codes
    rather than repeating one constant value per text -- a vector with the
    same value in every dimension is cosine-parallel to every other nonzero
    one, which would make vector search collapse into ties regardless of
    content.
    """

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text: str) -> list[float]:
        seed = sum(ord(character) for character in text) or 1
        return [float((seed * (dimension + 1)) % 97) for dimension in range(self.dimensions)]


class FakeLLMProvider(LLMProvider):
    """A scripted LLMProvider for tests that shouldn't need a real API call.

    Returns `responses` in order, one per `generate` call; once exhausted,
    repeats the last response. Records every call's messages for assertions
    on retry behavior.
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[list[LLMMessage]] = []

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        self.calls.append(messages)
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return LLMResponse(
            text=self._responses[index], model="fake-model", input_tokens=0, output_tokens=0
        )
