import pytest

from app.config import Settings, get_settings
from app.dependencies import get_cached_embedding_provider, get_cached_llm_provider
from app.providers.embedding.local_bge_provider import LocalBGEEmbeddingProvider
from app.providers.llm.gemini_provider import GeminiLLMProvider


def test_get_cached_embedding_provider_builds_from_settings_and_caches_the_instance() -> None:
    """Exercises the real production wiring (the integration tests override
    this dependency with a fake instead) -- both lru_caches are cleared
    around the assertion so this doesn't leak into other tests."""
    get_cached_embedding_provider.cache_clear()
    get_settings.cache_clear()
    try:
        provider = get_cached_embedding_provider()

        assert isinstance(provider, LocalBGEEmbeddingProvider)
        assert get_cached_embedding_provider() is provider
    finally:
        get_cached_embedding_provider.cache_clear()
        get_settings.cache_clear()


def test_get_cached_llm_provider_builds_from_settings_and_caches_the_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.dependencies.get_settings",
        lambda: Settings(_env_file=None, llm_provider="gemini", gemini_api_key="fake-key"),  # type: ignore[call-arg]
    )
    get_cached_llm_provider.cache_clear()
    try:
        provider = get_cached_llm_provider()

        assert isinstance(provider, GeminiLLMProvider)
        assert get_cached_llm_provider() is provider
    finally:
        get_cached_llm_provider.cache_clear()
