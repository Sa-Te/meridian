from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.providers.embedding.voyage_provider import VoyageEmbeddingProvider


def _provider() -> VoyageEmbeddingProvider:
    return VoyageEmbeddingProvider(api_key="fake-key", model="voyage-3-lite")


async def test_embed_passes_texts_and_document_input_type() -> None:
    provider = _provider()
    provider._client.embed = AsyncMock(
        return_value=SimpleNamespace(embeddings=[[0.1, 0.2], [0.3, 0.4]])
    )

    vectors = await provider.embed(["first chunk", "second chunk"])

    provider._client.embed.assert_awaited_once_with(
        ["first chunk", "second chunk"], model="voyage-3-lite", input_type="document"
    )
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


async def test_embed_normalizes_quantized_int_output_to_float() -> None:
    """Voyage's response may carry int-quantized embeddings; callers (pgvector
    storage, cosine-similarity math) expect float vectors regardless."""
    provider = _provider()
    provider._client.embed = AsyncMock(return_value=SimpleNamespace(embeddings=[[1, 0, -1]]))

    vectors = await provider.embed(["a chunk"])

    assert vectors == [[1.0, 0.0, -1.0]]
    assert all(isinstance(value, float) for value in vectors[0])
