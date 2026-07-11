"""Integration test for the real local embedding model (ADR-0004). Downloads
and loads BAAI/bge-base-en-v1.5 on first run -- slower than the rest of the
suite, and needs network access the first time it runs in a fresh
environment (the model is then cached on disk).
"""

import math

from app.providers.embedding.local_bge_provider import LocalBGEEmbeddingProvider


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(y * y for y in b))
    return dot_product / (magnitude_a * magnitude_b)


async def test_paraphrase_similarity_exceeds_unrelated_sentence_similarity() -> None:
    provider = LocalBGEEmbeddingProvider()
    sentences = [
        "The quarterly earnings report exceeded analyst expectations.",
        "Quarterly earnings came in higher than analysts had predicted.",
        "The chef added fresh basil to the simmering tomato sauce.",
    ]

    embeddings = await provider.embed(sentences)

    assert len(embeddings) == 3
    assert all(len(vector) == 768 for vector in embeddings)

    paraphrase_similarity = _cosine_similarity(embeddings[0], embeddings[1])
    unrelated_similarity = _cosine_similarity(embeddings[0], embeddings[2])

    assert paraphrase_similarity > unrelated_similarity
