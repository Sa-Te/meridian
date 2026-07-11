from functools import lru_cache

from app.config import get_settings
from app.providers.embedding.base import EmbeddingProvider
from app.providers.embedding.factory import get_embedding_provider
from app.providers.llm.base import LLMProvider
from app.providers.llm.factory import get_llm_provider


@lru_cache
def get_cached_embedding_provider() -> EmbeddingProvider:
    """A single EmbeddingProvider instance shared across requests, so a
    local model (if selected) is loaded once, not per request."""
    return get_embedding_provider(get_settings())


@lru_cache
def get_cached_llm_provider() -> LLMProvider:
    """A single LLMProvider instance shared across requests."""
    return get_llm_provider(get_settings())
