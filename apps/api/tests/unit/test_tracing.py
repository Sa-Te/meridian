import numpy as np
import pytest
from pydantic import BaseModel

from app.models.orm import TraceOutcome
from app.providers.diarization.base import DiarizationSegment
from app.providers.llm.base import LLMMessage, LLMResponse
from app.providers.transcription.base import TranscriptionSegment
from app.services.tracing import (
    TraceRecorder,
    TracingDiarizationProvider,
    TracingEmbeddingProvider,
    TracingLLMProvider,
    TracingTranscriptionProvider,
)
from tests.fakes import (
    FakeDiarizationProvider,
    FakeEmbeddingProvider,
    FakeLLMProvider,
    FakeTranscriptionProvider,
)


class _Payload(BaseModel):
    value: str


async def test_stage_records_name_metadata_and_nonnegative_duration() -> None:
    recorder = TraceRecorder(endpoint="POST /ask")

    async with recorder.stage("hybrid_search", top_k=8) as metadata:
        metadata["retrieved_count"] = 3

    assert len(recorder.stages) == 1
    stage = recorder.stages[0]
    assert stage.name == "hybrid_search"
    assert stage.metadata == {"top_k": 8, "retrieved_count": 3}
    assert stage.duration_ms >= 0.0


async def test_stage_records_error_and_reraises() -> None:
    recorder = TraceRecorder(endpoint="POST /ask")

    with pytest.raises(ValueError, match="boom"):
        async with recorder.stage("generate_answer"):
            raise ValueError("boom")

    assert len(recorder.stages) == 1
    assert recorder.stages[0].metadata["error"] == "boom"


async def test_multiple_stages_accumulate_in_order() -> None:
    recorder = TraceRecorder(endpoint="POST /ask")

    async with recorder.stage("embed"):
        pass
    async with recorder.stage("hybrid_search"):
        pass

    assert [stage.name for stage in recorder.stages] == ["embed", "hybrid_search"]


def test_to_orm_builds_trace_with_accumulated_fields() -> None:
    recorder = TraceRecorder(endpoint="POST /ask")
    recorder.record_llm_usage(
        LLMResponse(text="hi", model="gemini-3.1-flash-lite", input_tokens=10, output_tokens=20)
    )
    recorder.record_llm_usage(
        LLMResponse(text="hi again", model="gemini-3.1-flash-lite", input_tokens=5, output_tokens=7)
    )

    trace = recorder.to_orm(outcome=TraceOutcome.ANSWERED)

    assert trace.endpoint == "POST /ask"
    assert trace.outcome == TraceOutcome.ANSWERED
    assert trace.input_tokens == 15
    assert trace.output_tokens == 27
    assert trace.models_used == ["gemini-3.1-flash-lite"]
    assert trace.total_duration_ms >= 0.0
    assert trace.stages == []


def test_record_model_used_without_llm_response_adds_no_tokens() -> None:
    recorder = TraceRecorder(endpoint="POST /meetings/ingest")
    recorder.record_model_used("gemini-3.1-flash-lite")

    trace = recorder.to_orm(outcome=TraceOutcome.ANSWERED)

    assert trace.models_used == ["gemini-3.1-flash-lite"]
    assert trace.input_tokens == 0
    assert trace.output_tokens == 0


async def test_tracing_embedding_provider_delegates_and_records_stage() -> None:
    recorder = TraceRecorder(endpoint="POST /ask")
    fake = FakeEmbeddingProvider(dimensions=4)
    provider = TracingEmbeddingProvider(fake, recorder)

    vectors = await provider.embed(["hello", "world"])

    assert len(vectors) == 2
    assert all(len(vector) == 4 for vector in vectors)
    assert fake.calls == [["hello", "world"]]  # the real call happened once, through the tracer
    assert len(recorder.stages) == 1
    embed_stage = recorder.stages[0]
    assert embed_stage.name == "embed"
    assert embed_stage.metadata["text_count"] == 2
    assert embed_stage.metadata["dimensions"] == 4


async def test_tracing_embedding_provider_records_zero_dimensions_for_empty_input() -> None:
    recorder = TraceRecorder(endpoint="POST /ask")
    provider = TracingEmbeddingProvider(FakeEmbeddingProvider(), recorder)

    vectors = await provider.embed([])

    assert vectors == []
    assert recorder.stages[0].metadata["dimensions"] == 0


async def test_tracing_llm_provider_generate_records_usage_and_stage() -> None:
    recorder = TraceRecorder(endpoint="POST /ask")
    fake = FakeLLMProvider(responses=["the answer"])
    provider = TracingLLMProvider(fake, recorder, model_name="fake-model")

    response = await provider.generate(messages=[LLMMessage(role="user", content="hi")])

    assert response.text == "the answer"
    assert len(fake.calls) == 1
    assert recorder.input_tokens == response.input_tokens
    assert recorder.output_tokens == response.output_tokens
    assert recorder.models_used == {"fake-model"}
    assert recorder.stages[0].name == "llm_generate"
    assert recorder.stages[0].metadata["model"] == "fake-model"


async def test_tracing_llm_provider_generate_structured_records_model_not_tokens() -> None:
    recorder = TraceRecorder(endpoint="POST /meetings/ingest")
    fake = FakeLLMProvider(structured_responses=[_Payload(value="x")])
    provider = TracingLLMProvider(fake, recorder, model_name="fake-model")

    result = await provider.generate_structured("a prompt", _Payload)

    assert result == _Payload(value="x")
    assert len(fake.structured_calls) == 1
    assert recorder.models_used == {"fake-model"}
    assert recorder.input_tokens == 0
    assert recorder.output_tokens == 0
    assert recorder.stages[0].name == "llm_generate_structured"
    assert recorder.stages[0].metadata["response_model"] == "_Payload"


async def test_tracing_llm_provider_records_error_on_generate_failure() -> None:
    recorder = TraceRecorder(endpoint="POST /ask")

    class _FailingProvider(FakeLLMProvider):
        async def generate(self, *args: object, **kwargs: object) -> LLMResponse:
            raise RuntimeError("vendor is down")

    provider = TracingLLMProvider(_FailingProvider(), recorder, model_name="fake-model")

    with pytest.raises(RuntimeError, match="vendor is down"):
        await provider.generate(messages=[LLMMessage(role="user", content="hi")])

    assert recorder.stages[0].metadata["error"] == "vendor is down"
    assert recorder.input_tokens == 0


async def test_tracing_transcription_provider_delegates_and_records_stage() -> None:
    recorder = TraceRecorder(endpoint="POST /meetings/ingest-audio")
    fake = FakeTranscriptionProvider(
        segments=[TranscriptionSegment(start_ts=0.0, end_ts=1.5, text="Hello.")]
    )
    provider = TracingTranscriptionProvider(fake, recorder)
    waveform = np.zeros(16_000, dtype=np.float32)

    segments = await provider.transcribe(waveform, sample_rate=16_000)

    assert segments[0].text == "Hello."
    assert fake.calls == [(waveform, 16_000)]
    assert recorder.stages[0].name == "transcribe"
    assert recorder.stages[0].metadata["sample_rate"] == 16_000
    assert recorder.stages[0].metadata["segment_count"] == 1


async def test_tracing_diarization_provider_delegates_and_records_stage() -> None:
    recorder = TraceRecorder(endpoint="POST /meetings/ingest-audio")
    fake = FakeDiarizationProvider(
        segments=[
            DiarizationSegment(start_ts=0.0, end_ts=2.0, speaker_label="SPEAKER_00"),
            DiarizationSegment(start_ts=2.0, end_ts=4.0, speaker_label="SPEAKER_01"),
        ]
    )
    provider = TracingDiarizationProvider(fake, recorder)
    waveform = np.zeros(16_000, dtype=np.float32)

    segments = await provider.diarize(waveform, sample_rate=16_000, min_speakers=1, max_speakers=3)

    assert len(segments) == 2
    assert fake.calls == [{"sample_rate": 16_000, "min_speakers": 1, "max_speakers": 3}]
    assert recorder.stages[0].name == "diarize"
    assert recorder.stages[0].metadata["segment_count"] == 2
    assert recorder.stages[0].metadata["distinct_speakers"] == 2
