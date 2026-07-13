import pytest

from app.config import Settings
from app.providers.diarization.factory import get_diarization_provider
from app.providers.diarization.pyannote_provider import PyannoteDiarizationProvider
from app.providers.transcription.factory import get_transcription_provider
from app.providers.transcription.faster_whisper_provider import FasterWhisperTranscriptionProvider


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type,call-arg]


def test_get_transcription_provider_returns_faster_whisper() -> None:
    provider = get_transcription_provider(_settings(whisper_model="small"))

    assert isinstance(provider, FasterWhisperTranscriptionProvider)
    assert provider._model_name == "small"


def test_get_diarization_provider_returns_pyannote_when_token_is_set() -> None:
    provider = get_diarization_provider(_settings(hf_token="fake-token"))

    assert isinstance(provider, PyannoteDiarizationProvider)


def test_get_diarization_provider_requires_hf_token() -> None:
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        get_diarization_provider(_settings(hf_token=None))
