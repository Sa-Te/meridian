from functools import lru_cache

from app.config import get_settings
from app.providers.embedding.base import EmbeddingProvider
from app.providers.embedding.factory import get_embedding_provider


@lru_cache
def get_cached_embedding_provider() -> EmbeddingProvider:
    """A single EmbeddingProvider instance shared across requests, so a
    local model (if selected) is loaded once, not per request."""
    return get_embedding_provider(get_settings())
