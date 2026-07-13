from app.config import Settings
from app.providers.transcription.base import TranscriptionProvider
from app.providers.transcription.faster_whisper_provider import FasterWhisperTranscriptionProvider


def get_transcription_provider(settings: Settings) -> TranscriptionProvider:
    """Instantiate the active TranscriptionProvider. faster-whisper is
    currently the only implementation (see docs/adr/0012 for why); the
    interface exists so an API-based provider is a config swap later, not
    a rewrite -- the same pattern as EmbeddingProvider/LLMProvider.
    """
    return FasterWhisperTranscriptionProvider(model_name=settings.whisper_model)
