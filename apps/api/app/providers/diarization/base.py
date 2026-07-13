from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class DiarizationSegment:
    """One speaker-attributed time segment from a diarization pass.

    speaker_label is the pipeline's own raw, internal label (e.g.
    "SPEAKER_00") -- stable within one diarization run, not a real name,
    and not necessarily stable across separate runs of the same audio.
    Resolving these into the stable, ordered "Speaker N" labels a Meeting
    actually stores is app/services/audio_alignment.py's job, not the
    provider's. See docs/adr/0012.
    """

    start_ts: float
    end_ts: float
    speaker_label: str


class DiarizationProvider(ABC):
    """Vendor-agnostic speaker-diarization interface (ADR-0002's pattern,
    applied to the audio pipeline -- see docs/adr/0012).

    Takes an already-decoded mono waveform, exactly like
    TranscriptionProvider -- decoding happens once in the audio-ingestion
    service and is shared between both providers.
    """

    @abstractmethod
    async def diarize(
        self,
        waveform: NDArray[np.float32],
        *,
        sample_rate: int,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[DiarizationSegment]:
        """Diarize a mono waveform, returning speaker segments in
        chronological order.

        min_speakers/max_speakers are an optional hint for a caller who
        already knows roughly how many distinct speakers to expect --
        unconstrained (the pipeline auto-detects) when omitted.
        """
        raise NotImplementedError
