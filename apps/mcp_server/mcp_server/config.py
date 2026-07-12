from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for the MCP server, sourced from environment variables
    and `.env`. The MCP server is a thin client of the FastAPI backend
    (docs/adr/0011) -- the only setting it needs is where that backend is.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    meridian_api_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL of the running Meridian FastAPI backend.",
    )
    request_timeout_seconds: float = Field(
        default=30.0,
        description="Timeout for HTTP calls from the MCP server to the backend.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
