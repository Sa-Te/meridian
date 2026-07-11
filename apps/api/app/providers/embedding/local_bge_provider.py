import asyncio

from sentence_transformers import SentenceTransformer

from app.providers.embedding.base import EmbeddingProvider

DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"


class LocalBGEEmbeddingProvider(EmbeddingProvider):
    """EmbeddingProvider backed by a local sentence-transformers model.

    The active default (ADR-0004) -- requires no external API key. The
    model is downloaded once on first use and cached on disk afterward;
    that first call is noticeably slower than every call after it.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        # normalize_embeddings=True: BGE is designed for cosine-similarity
        # retrieval, and pgvector's cosine operator is cheapest against
        # pre-normalized vectors.
        embeddings = self._get_model().encode(texts, normalize_embeddings=True)
        return [embedding.tolist() for embedding in embeddings]
