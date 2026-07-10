from app.config import Settings
from app.providers.llm.anthropic_provider import AnthropicLLMProvider
from app.providers.llm.base import LLMProvider
from app.providers.llm.gemini_provider import GeminiLLMProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Instantiate the active LLMProvider per LLM_PROVIDER. See ADR-0013."""
    provider_name = settings.llm_provider.lower()

    if provider_name == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("LLM_PROVIDER=gemini requires GEMINI_API_KEY to be set.")
        return GeminiLLMProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)

    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY to be set.")
        return AnthropicLLMProvider(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Expected 'gemini' or 'anthropic'."
    )
