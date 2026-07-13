import asyncio

import numpy as np
from faster_whisper import WhisperModel
from numpy.typing import NDArray

from app.providers.transcription.base import TranscriptionProvider, TranscriptionSegment

DEFAULT_MODEL = "small"
_REQUIRED_SAMPLE_RATE = 16_000


class FasterWhisperTranscriptionProvider(TranscriptionProvider):
    """TranscriptionProvider backed by a local faster-whisper model.

    The active default (ADR-0012) -- requires no external API key or
    network access after the model is first downloaded and cached. CPU
    inference via int8 quantization (compute_type="int8"), matching this
    project's CPU-only deployment target (see the Dockerfile).
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(self._model_name, device="cpu", compute_type="int8")
        return self._model

    async def transcribe(
        self, waveform: NDArray[np.float32], *, sample_rate: int
    ) -> list[TranscriptionSegment]:
        return await asyncio.to_thread(self._transcribe_sync, waveform, sample_rate)

    def _transcribe_sync(
        self, waveform: NDArray[np.float32], sample_rate: int
    ) -> list[TranscriptionSegment]:
        if sample_rate != _REQUIRED_SAMPLE_RATE:
            raise ValueError(
                f"faster-whisper requires {_REQUIRED_SAMPLE_RATE}Hz audio, got {sample_rate}Hz."
            )
        segments, _info = self._get_model().transcribe(waveform, language="en")
        return [
            TranscriptionSegment(
                start_ts=segment.start, end_ts=segment.end, text=segment.text.strip()
            )
            for segment in segments
        ]
