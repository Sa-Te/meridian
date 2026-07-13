from app.config import Settings
from app.providers.diarization.base import DiarizationProvider
from app.providers.diarization.pyannote_provider import PyannoteDiarizationProvider


def get_diarization_provider(settings: Settings) -> DiarizationProvider:
    """Instantiate the active DiarizationProvider. pyannote.audio is
    currently the only implementation (see docs/adr/0012). Raises clearly,
    the same way get_llm_provider does for a missing GEMINI_API_KEY, rather
    than failing deep inside pyannote.audio with a confusing HTTP error.
    """
    if not settings.hf_token:
        raise RuntimeError(
            "POST /meetings/ingest-audio requires HF_TOKEN -- a HuggingFace access "
            "token with pyannote.audio's gated model terms accepted. See docs/adr/0012."
        )
    return PyannoteDiarizationProvider(
        hf_token=settings.hf_token, model_name=settings.diarization_model
    )
