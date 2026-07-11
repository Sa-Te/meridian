from app.config import Settings
from app.providers.embedding.base import EmbeddingProvider
from app.providers.embedding.local_bge_provider import LocalBGEEmbeddingProvider
from app.providers.embedding.voyage_provider import VoyageEmbeddingProvider


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Instantiate the active EmbeddingProvider per EMBEDDING_PROVIDER. See ADR-0004."""
    provider_name = settings.embedding_provider.lower()

    if provider_name == "local":
        return LocalBGEEmbeddingProvider()

    if provider_name == "voyage":
        if not settings.voyage_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=voyage requires VOYAGE_API_KEY to be set.")
        return VoyageEmbeddingProvider(api_key=settings.voyage_api_key, model=settings.voyage_model)

    if provider_name == "openai":
        raise NotImplementedError(
            "EMBEDDING_PROVIDER=openai is documented as a future option but not implemented "
            "yet. Use 'local' or 'voyage'."
        )

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER '{settings.embedding_provider}'. Expected 'local' or 'voyage'."
    )
