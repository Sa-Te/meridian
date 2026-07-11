from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="development", description="Deployment environment name.")
    log_level: str = Field(default="INFO", description="Root logging level.")
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated origins allowed to call the API from a browser.",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://meridian:meridian@postgres:5432/meridian",
        description="Async SQLAlchemy connection string for the pgvector-enabled Postgres "
        "instance. See ADR-0004.",
    )

    llm_provider: str = Field(
        default="gemini",
        description="Active LLMProvider implementation: 'gemini' or 'anthropic'. See ADR-0013.",
    )
    gemini_api_key: str | None = Field(
        default=None,
        description="Required when LLM_PROVIDER=gemini (the default). Used for generation "
        "and the eval LLM-judge.",
    )
    gemini_model: str = Field(
        default="gemini-3.1-flash-lite",
        description="Gemini model used for generation and the eval LLM-judge. See ADR-0013.",
    )
    anthropic_api_key: str | None = Field(
        default=None,
        description="Optional. Only required when LLM_PROVIDER=anthropic; not on the default "
        "code path. See ADR-0013.",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-5",
        description="Anthropic model used only when LLM_PROVIDER=anthropic.",
    )

    embedding_provider: str = Field(
        default="local",
        description="Active EmbeddingProvider implementation: 'local' or 'voyage'. See ADR-0004.",
    )
    voyage_api_key: str | None = Field(
        default=None,
        description="Required when EMBEDDING_PROVIDER=voyage; not on the default code path.",
    )
    voyage_model: str = Field(
        default="voyage-3-lite",
        description="Voyage embedding model used only when EMBEDDING_PROVIDER=voyage.",
    )

    retrieval_top_k: int = Field(
        default=8,
        description="Number of fused chunks passed to the LLM for answer generation. See ADR-0007.",
    )
    retrieval_candidate_pool_size: int = Field(
        default=25,
        description="Number of candidates fetched from each of vector search and "
        "full-text search before fusion. See ADR-0007.",
    )
    retrieval_vector_weight: float = Field(
        default=0.6,
        description="Weight given to the normalized cosine-similarity score during "
        "fusion. See ADR-0007.",
    )
    retrieval_text_weight: float = Field(
        default=0.4,
        description="Weight given to the normalized full-text rank score during "
        "fusion. See ADR-0007.",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
