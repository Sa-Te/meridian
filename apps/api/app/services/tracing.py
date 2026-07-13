"""Request tracing: TraceRecorder accumulates named stage timings for one
request, and TracingEmbeddingProvider/TracingLLMProvider are decorators
around the existing provider ports that record a stage automatically on
every real embedding/LLM call. See docs/adr/0010.

Instrumentation lives entirely at this seam (provider decorators) and at
router call sites using TraceRecorder.stage directly, so no business-logic
service (retrieval, answer_generation, extraction, ingestion, guardrails)
needs to know tracing exists at all.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.models.orm import Trace, TraceOutcome
from app.providers.diarization.base import DiarizationProvider, DiarizationSegment
from app.providers.embedding.base import EmbeddingProvider
from app.providers.llm.base import LLMMessage, LLMProvider, LLMResponse, SchemaT
from app.providers.transcription.base import TranscriptionProvider, TranscriptionSegment


@dataclass(frozen=True)
class TraceStage:
    """One recorded stage: a named span of work within a traced request."""

    name: str
    started_at: datetime
    duration_ms: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class TraceRecorder:
    """Accumulates stage timings, LLM token usage, and models used for one
    request, from construction until `to_orm` builds the row to persist.
    """

    def __init__(self, *, endpoint: str) -> None:
        self.endpoint = endpoint
        self.stages: list[TraceStage] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.models_used: set[str] = set()
        self._started_at_monotonic = time.monotonic()

    @asynccontextmanager
    async def stage(self, name: str, **metadata: Any) -> AsyncIterator[dict[str, Any]]:
        """Records one named stage. `metadata` seeds the stage's recorded
        metadata; the caller may also mutate the yielded dict in place to
        add detail discovered during the stage (e.g. a result count). An
        exception raised inside the block is recorded into the stage's
        metadata under "error" and re-raised unchanged -- this only
        observes the caller's error handling, never replaces it.
        """
        started_at = datetime.now(UTC)
        started_monotonic = time.monotonic()
        stage_metadata = dict(metadata)
        try:
            yield stage_metadata
        except Exception as error:
            stage_metadata["error"] = str(error)
            raise
        finally:
            duration_ms = (time.monotonic() - started_monotonic) * 1000
            self.stages.append(
                TraceStage(
                    name=name,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    metadata=stage_metadata,
                )
            )

    def record_llm_usage(self, response: LLMResponse) -> None:
        """Adds one generate() call's real, per-response token usage."""
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.models_used.add(response.model)

    def record_model_used(self, model: str) -> None:
        """Records that a model was invoked without per-call token usage --
        generate_structured (extraction) returns no LLMResponse to read
        tokens from. See docs/adr/0010.
        """
        self.models_used.add(model)

    def to_orm(self, *, outcome: TraceOutcome) -> Trace:
        return Trace(
            endpoint=self.endpoint,
            stages=[stage.to_dict() for stage in self.stages],
            total_duration_ms=(time.monotonic() - self._started_at_monotonic) * 1000,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            models_used=sorted(self.models_used),
            outcome=outcome,
        )


class TracingEmbeddingProvider(EmbeddingProvider):
    """Decorator around a real EmbeddingProvider recording one "embed"
    stage per call, so ingestion/retrieval code calling `.embed(...)` needs
    no changes at all to become traced.
    """

    def __init__(self, wrapped: EmbeddingProvider, recorder: TraceRecorder) -> None:
        self._wrapped = wrapped
        self._recorder = recorder

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with self._recorder.stage("embed", text_count=len(texts)) as metadata:
            vectors = await self._wrapped.embed(texts)
            metadata["dimensions"] = len(vectors[0]) if vectors else 0
            return vectors


class TracingLLMProvider(LLMProvider):
    """Decorator around a real LLMProvider recording one stage per
    generate()/generate_structured() call, accumulating token usage and
    models used onto the shared TraceRecorder.

    model_name is passed in explicitly (from Settings, at construction)
    rather than read off the wrapped provider, so models_used is populated
    even for generate_structured calls, whose LLMResponse-less return
    value carries no usage/model metadata of its own. See docs/adr/0010.
    """

    def __init__(self, wrapped: LLMProvider, recorder: TraceRecorder, *, model_name: str) -> None:
        self._wrapped = wrapped
        self._recorder = recorder
        self._model_name = model_name

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        async with self._recorder.stage("llm_generate") as metadata:
            response = await self._wrapped.generate(
                messages, system=system, max_tokens=max_tokens, temperature=temperature
            )
            self._recorder.record_llm_usage(response)
            metadata["model"] = response.model
            metadata["input_tokens"] = response.input_tokens
            metadata["output_tokens"] = response.output_tokens
            return response

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[SchemaT],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> SchemaT:
        async with self._recorder.stage("llm_generate_structured") as metadata:
            self._recorder.record_model_used(self._model_name)
            metadata["model"] = self._model_name
            metadata["response_model"] = response_model.__name__
            return await self._wrapped.generate_structured(
                prompt,
                response_model,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )


class TracingTranscriptionProvider(TranscriptionProvider):
    """Decorator around a real TranscriptionProvider recording one
    "transcribe" stage per call. See docs/adr/0012.
    """

    def __init__(self, wrapped: TranscriptionProvider, recorder: TraceRecorder) -> None:
        self._wrapped = wrapped
        self._recorder = recorder

    async def transcribe(
        self, waveform: NDArray[np.float32], *, sample_rate: int
    ) -> list[TranscriptionSegment]:
        async with self._recorder.stage("transcribe", sample_rate=sample_rate) as metadata:
            segments = await self._wrapped.transcribe(waveform, sample_rate=sample_rate)
            metadata["segment_count"] = len(segments)
            return segments


class TracingDiarizationProvider(DiarizationProvider):
    """Decorator around a real DiarizationProvider recording one
    "diarize" stage per call. See docs/adr/0012.
    """

    def __init__(self, wrapped: DiarizationProvider, recorder: TraceRecorder) -> None:
        self._wrapped = wrapped
        self._recorder = recorder

    async def diarize(
        self,
        waveform: NDArray[np.float32],
        *,
        sample_rate: int,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[DiarizationSegment]:
        async with self._recorder.stage("diarize", sample_rate=sample_rate) as metadata:
            segments = await self._wrapped.diarize(
                waveform,
                sample_rate=sample_rate,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
            )
            metadata["segment_count"] = len(segments)
            metadata["distinct_speakers"] = len({segment.speaker_label for segment in segments})
            return segments
