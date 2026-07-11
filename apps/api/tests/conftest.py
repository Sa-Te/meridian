import pytest

from tests.fakes import FakeEmbeddingProvider


@pytest.fixture
def fake_embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()
