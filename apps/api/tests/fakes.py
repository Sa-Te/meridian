"""Shared test doubles, importable from both tests/unit and tests/integration."""

from app.providers.embedding.base import EmbeddingProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    """A deterministic EmbeddingProvider for tests that shouldn't need to
    load a real model or call a real API. Not a real embedding -- just a
    fixed-dimension vector derived from each text's length, enough to
    exercise the pipeline's plumbing (ordering, dimensionality, storage).
    """

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(len(text) % 7)] * self.dimensions for text in texts]
