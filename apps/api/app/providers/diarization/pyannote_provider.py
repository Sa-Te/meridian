import asyncio
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from pyannote.audio import Pipeline

from app.providers.diarization.base import DiarizationProvider, DiarizationSegment

DEFAULT_MODEL = "pyannote/speaker-diarization-3.1"


class PyannoteDiarizationProvider(DiarizationProvider):
    """DiarizationProvider backed by pyannote.audio's pretrained pipeline.

    The active default (ADR-0012) -- requires HF_TOKEN (a HuggingFace
    access token with the pipeline's gated model terms accepted). This is
    the one place in the whole system that requires an external dependency
    beyond GEMINI_API_KEY, and only for this optional audio-ingestion path;
    see ADR-0012 for why that trade-off was accepted.
    """

    def __init__(self, hf_token: str, model_name: str = DEFAULT_MODEL) -> None:
        self._hf_token = hf_token
        self._model_name = model_name
        self._pipeline: Pipeline | None = None

    def _get_pipeline(self) -> Pipeline:
        if self._pipeline is None:
            pipeline = Pipeline.from_pretrained(self._model_name, token=self._hf_token)
            if pipeline is None:
                raise RuntimeError(
                    f"Failed to load diarization pipeline {self._model_name!r} -- "
                    "check that HF_TOKEN has accepted the model's gated terms."
                )
            self._pipeline = pipeline
        return self._pipeline

    async def diarize(
        self,
        waveform: NDArray[np.float32],
        *,
        sample_rate: int,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[DiarizationSegment]:
        return await asyncio.to_thread(
            self._diarize_sync, waveform, sample_rate, min_speakers, max_speakers
        )

    def _diarize_sync(
        self,
        waveform: NDArray[np.float32],
        sample_rate: int,
        min_speakers: int | None,
        max_speakers: int | None,
    ) -> list[DiarizationSegment]:
        tensor = torch.from_numpy(waveform).unsqueeze(0)
        kwargs: dict[str, Any] = {}
        if min_speakers is not None:
            kwargs["min_speakers"] = min_speakers
        if max_speakers is not None:
            kwargs["max_speakers"] = max_speakers

        output = self._get_pipeline()({"waveform": tensor, "sample_rate": sample_rate}, **kwargs)
        # .speaker_diarization (not .exclusive_speaker_diarization) keeps
        # overlapping speech turns intact -- app/services/audio_alignment.py
        # needs to see genuine overlap to apply its contested-attribution
        # policy, not have pyannote silently resolve it first.
        # pyannote.audio's bundled type stubs still reflect the pre-4.0
        # Pipeline.__call__ return type (a bare Annotation/Iterator), not
        # the current DiarizeOutput dataclass this actually returns.
        annotation = output.speaker_diarization  # type: ignore[union-attr]
        return [
            DiarizationSegment(start_ts=turn.start, end_ts=turn.end, speaker_label=speaker)
            for turn, _, speaker in annotation.itertracks(yield_label=True)
        ]
