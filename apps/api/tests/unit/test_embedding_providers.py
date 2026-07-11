import pytest

from app.config import Settings
from app.providers.embedding.factory import get_embedding_provider
from app.providers.embedding.local_bge_provider import LocalBGEEmbeddingProvider
from app.providers.embedding.voyage_provider import VoyageEmbeddingProvider
from tests.fakes import FakeEmbeddingProvider


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type,call-arg]


async def test_fake_provider_satisfies_the_interface_contract() -> None:
    """A conforming EmbeddingProvider returns one vector per input text, of
    a consistent dimension, in the same order as the input -- proven here
    with a fake so calling code can be tested without a real model/API."""
    provider = FakeEmbeddingProvider(dimensions=4)

    vectors = await provider.embed(["short", "a bit longer text"])

    assert len(vectors) == 2
    assert all(len(vector) == 4 for vector in vectors)
    # Order preserved: the two distinct-length inputs map to distinct vectors.
    assert vectors[0] != vectors[1]


async def test_fake_provider_handles_empty_input() -> None:
    provider = FakeEmbeddingProvider()

    assert await provider.embed([]) == []


def test_defaults_to_local_provider() -> None:
    settings = _settings()

    assert settings.embedding_provider == "local"
    provider = get_embedding_provider(settings)

    assert isinstance(provider, LocalBGEEmbeddingProvider)


def test_voyage_selected_via_env_returns_voyage_provider() -> None:
    settings = _settings(embedding_provider="voyage", voyage_api_key="fake-key")

    provider = get_embedding_provider(settings)

    assert isinstance(provider, VoyageEmbeddingProvider)


def test_voyage_requires_api_key() -> None:
    settings = _settings(embedding_provider="voyage", voyage_api_key=None)

    with pytest.raises(RuntimeError, match="VOYAGE_API_KEY"):
        get_embedding_provider(settings)


def test_openai_raises_not_implemented() -> None:
    settings = _settings(embedding_provider="openai")

    with pytest.raises(NotImplementedError, match="not implemented"):
        get_embedding_provider(settings)


def test_unknown_provider_raises_value_error() -> None:
    settings = _settings(embedding_provider="made-up")

    with pytest.raises(ValueError, match="Unknown EMBEDDING_PROVIDER"):
        get_embedding_provider(settings)


def test_provider_name_is_case_insensitive() -> None:
    settings = _settings(embedding_provider="LOCAL")

    provider = get_embedding_provider(settings)

    assert isinstance(provider, LocalBGEEmbeddingProvider)
