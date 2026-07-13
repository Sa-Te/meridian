from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class TranscriptionSegment:
    """One transcribed segment, with real (sub-second) start/end timestamps
    in elapsed seconds from the start of the audio -- unlike a hand-typed
    text transcript (app/services/transcript_parser.py), which only ever
    carries one timestamp per turn. See docs/adr/0012.
    """

    start_ts: float
    end_ts: float
    text: str


class TranscriptionProvider(ABC):
    """Vendor-agnostic speech-to-text interface (ADR-0002's pattern,
    applied to the audio pipeline -- see docs/adr/0012).

    Takes an already-decoded mono waveform rather than a file path or raw
    bytes: decoding is the audio-ingestion service's job (app/services/
    audio_ingestion.py), done once and shared with DiarizationProvider,
    not each provider's own concern.
    """

    @abstractmethod
    async def transcribe(
        self, waveform: NDArray[np.float32], *, sample_rate: int
    ) -> list[TranscriptionSegment]:
        """Transcribe a mono waveform, returning segments in chronological
        order."""
        raise NotImplementedError
