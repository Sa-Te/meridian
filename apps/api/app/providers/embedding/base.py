from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Vendor-agnostic text-embedding interface (ADR-0002, ADR-0004).

    Concrete implementations (a local sentence-transformers model, Voyage
    AI) are selected at runtime via EMBEDDING_PROVIDER -- see factory.py.
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning one vector per input text, in
        the same order as the input."""
        raise NotImplementedError
