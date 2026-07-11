from voyageai.client_async import AsyncClient

from app.providers.embedding.base import EmbeddingProvider

DEFAULT_MODEL = "voyage-3-lite"


class VoyageEmbeddingProvider(EmbeddingProvider):
    """EmbeddingProvider backed by the Voyage AI API.

    The higher-recall, paid alternative to the local default (ADR-0004) --
    requires VOYAGE_API_KEY. Selected via EMBEDDING_PROVIDER=voyage.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = AsyncClient(api_key=api_key)
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # input_type="document" tells Voyage these are corpus text being
        # indexed, not a search query -- Voyage's models embed the two
        # differently for better retrieval quality.
        result = await self._client.embed(texts, model=self._model, input_type="document")
        # result.embeddings is typed as list[list[float]] | list[list[int]]
        # (Voyage supports quantized int output dtypes); normalize to float.
        return [[float(value) for value in vector] for vector in result.embeddings]
