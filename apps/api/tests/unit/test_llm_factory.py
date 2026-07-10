import pytest

from app.config import Settings
from app.providers.llm.anthropic_provider import AnthropicLLMProvider
from app.providers.llm.factory import get_llm_provider
from app.providers.llm.gemini_provider import GeminiLLMProvider


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type,call-arg]


def test_defaults_to_gemini() -> None:
    settings = _settings(gemini_api_key="fake-key")

    assert settings.llm_provider == "gemini"
    provider = get_llm_provider(settings)

    assert isinstance(provider, GeminiLLMProvider)


def test_gemini_requires_api_key() -> None:
    settings = _settings(llm_provider="gemini", gemini_api_key=None)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        get_llm_provider(settings)


def test_anthropic_selected_via_env_returns_anthropic_provider() -> None:
    settings = _settings(llm_provider="anthropic", anthropic_api_key="fake-key")

    provider = get_llm_provider(settings)

    assert isinstance(provider, AnthropicLLMProvider)


def test_anthropic_requires_api_key() -> None:
    settings = _settings(llm_provider="anthropic", anthropic_api_key=None)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        get_llm_provider(settings)


def test_gemini_selection_does_not_require_anthropic_key() -> None:
    settings = _settings(llm_provider="gemini", gemini_api_key="fake-key", anthropic_api_key=None)

    provider = get_llm_provider(settings)

    assert isinstance(provider, GeminiLLMProvider)


def test_unknown_provider_raises_value_error() -> None:
    settings = _settings(llm_provider="openai", gemini_api_key="fake-key")

    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_llm_provider(settings)


def test_provider_name_is_case_insensitive() -> None:
    settings = _settings(llm_provider="GEMINI", gemini_api_key="fake-key")

    provider = get_llm_provider(settings)

    assert isinstance(provider, GeminiLLMProvider)
