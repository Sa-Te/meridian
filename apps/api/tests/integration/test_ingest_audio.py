"""Integration tests for POST /meetings/ingest-audio. Requires a real
Postgres database migrated to head.

Most tests here use FakeTranscriptionProvider/FakeDiarizationProvider (see
tests/fakes.py) to prove the decode -> transcribe + diarize -> align ->
ingest wiring and the endpoint's own validation, without a real model or
network call. The one exception, at the bottom of this file, runs the
real faster-whisper + pyannote.audio pipeline against a synthesized
multi-speaker audio fixture -- skipped automatically without a real
HF_TOKEN, the same convention tests/integration/test_extraction.py already
uses for its one real-Gemini-call test. See docs/adr/0012.
"""

from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.config import get_settings
from app.db import async_session_factory, engine
from app.dependencies import (
    get_cached_diarization_provider,
    get_cached_embedding_provider,
    get_cached_llm_provider,
    get_cached_transcription_provider,
)
from app.main import app
from app.models.orm import Meeting, Trace
from app.providers.diarization.base import DiarizationSegment
from app.providers.diarization.pyannote_provider import PyannoteDiarizationProvider
from app.providers.transcription.base import TranscriptionSegment
from app.providers.transcription.faster_whisper_provider import FasterWhisperTranscriptionProvider
from app.repositories.meeting_repository import MeetingRepository
from app.services.audio_alignment import UNKNOWN_SPEAKER_LABEL
from app.services.extraction import _LLMExtractionPayload
from tests.fakes import (
    FakeDiarizationProvider,
    FakeEmbeddingProvider,
    FakeLLMProvider,
    FakeTranscriptionProvider,
)

_EMPTY_EXTRACTION = _LLMExtractionPayload(decisions=[], action_items=[])

_FIXTURE_DIR = Path(__file__).resolve().parents[4] / "data" / "audio"
_FIXTURE_WAV = _FIXTURE_DIR / "test_multi_speaker_sample.wav"


def _wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 16_000) -> bytes:
    buffer = BytesIO()
    sf.write(
        buffer,
        np.zeros(int(duration_seconds * sample_rate), dtype=np.float32),
        sample_rate,
        format="WAV",
    )
    return buffer.getvalue()


def _override_providers(
    *,
    transcription: FakeTranscriptionProvider | None = None,
    diarization: FakeDiarizationProvider | None = None,
) -> None:
    app.dependency_overrides[get_cached_embedding_provider] = FakeEmbeddingProvider
    app.dependency_overrides[get_cached_llm_provider] = lambda: FakeLLMProvider(
        structured_responses=[_EMPTY_EXTRACTION]
    )
    app.dependency_overrides[get_cached_transcription_provider] = lambda: (
        transcription if transcription is not None else FakeTranscriptionProvider()
    )
    app.dependency_overrides[get_cached_diarization_provider] = lambda: (
        diarization if diarization is not None else FakeDiarizationProvider()
    )


def _clear_overrides() -> None:
    for dependency in (
        get_cached_embedding_provider,
        get_cached_llm_provider,
        get_cached_transcription_provider,
        get_cached_diarization_provider,
    ):
        app.dependency_overrides.pop(dependency, None)


@pytest.fixture(autouse=True)
async def _clean_meetings_table() -> None:
    yield
    async with engine.begin() as connection:
        await connection.execute(delete(Meeting))
        await connection.execute(delete(Trace))


async def test_ingest_audio_endpoint_returns_meeting_id_and_chunk_count() -> None:
    transcription = FakeTranscriptionProvider(
        segments=[
            TranscriptionSegment(start_ts=0.0, end_ts=2.0, text="Hello there."),
            TranscriptionSegment(start_ts=2.0, end_ts=4.0, text="Hi, good to see you."),
        ]
    )
    diarization = FakeDiarizationProvider(
        segments=[
            DiarizationSegment(start_ts=0.0, end_ts=2.0, speaker_label="SPEAKER_00"),
            DiarizationSegment(start_ts=2.0, end_ts=4.0, speaker_label="SPEAKER_01"),
        ]
    )
    _override_providers(transcription=transcription, diarization=diarization)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/meetings/ingest-audio",
                files={"file": ("2026-01-14_call.wav", _wav_bytes(4.0), "audio/wav")},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] == 2
    assert body["decision_count"] == 0
    assert body["action_item_count"] == 0

    async with async_session_factory() as session:
        fetched = await MeetingRepository(session).get_by_id(body["meeting_id"])
    assert fetched is not None
    assert {chunk.speaker for chunk in fetched.chunks} == {"Speaker 1", "Speaker 2"}
    assert all(chunk.embedding is not None for chunk in fetched.chunks)


async def test_ingest_audio_labels_low_confidence_segments_as_unknown_speaker() -> None:
    transcription = FakeTranscriptionProvider(
        segments=[TranscriptionSegment(start_ts=0.0, end_ts=0.3, text="Um.")]
    )
    diarization = FakeDiarizationProvider(segments=[])  # nothing overlaps -> Rule 2
    _override_providers(transcription=transcription, diarization=diarization)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/meetings/ingest-audio",
                files={"file": ("2026-01-14_call.wav", _wav_bytes(1.0), "audio/wav")},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    async with async_session_factory() as session:
        fetched = await MeetingRepository(session).get_by_id(response.json()["meeting_id"])
    assert fetched is not None
    assert fetched.chunks[0].speaker == UNKNOWN_SPEAKER_LABEL


async def test_ingest_audio_endpoint_passes_speaker_count_hints_through() -> None:
    diarization = FakeDiarizationProvider(segments=[])
    _override_providers(diarization=diarization)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/meetings/ingest-audio",
                params={"min_speakers": 2, "max_speakers": 4},
                files={"file": ("2026-01-14_call.wav", _wav_bytes(1.0), "audio/wav")},
            )
    finally:
        _clear_overrides()

    assert diarization.calls == [{"sample_rate": 16_000, "min_speakers": 2, "max_speakers": 4}]


async def test_ingest_audio_endpoint_rejects_unsupported_extension() -> None:
    _override_providers()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/meetings/ingest-audio",
                files={"file": ("2026-01-14_call.mp3", _wav_bytes(1.0), "audio/mpeg")},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 422
    assert "mp3" in response.json()["detail"]


async def test_ingest_audio_endpoint_rejects_unparseable_filename() -> None:
    _override_providers()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/meetings/ingest-audio",
                files={"file": ("not-a-dated-filename.wav", _wav_bytes(1.0), "audio/wav")},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 422


async def test_ingest_audio_endpoint_rejects_undecodable_audio_content() -> None:
    _override_providers()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/meetings/ingest-audio",
                files={"file": ("2026-01-14_call.wav", b"not a real wav file", "audio/wav")},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 422
    assert "decode" in response.json()["detail"].lower()


# --- The one real-model test in this file -----------------------------------

_skip_without_hf_token = pytest.mark.skipif(
    not get_settings().hf_token, reason="requires a real HF_TOKEN (see .env)"
)


@_skip_without_hf_token
async def test_real_pipeline_transcribes_and_diarizes_the_sample_recording() -> None:
    """Runs the real faster-whisper + pyannote.audio pipeline (no fakes)
    against data/audio/test_multi_speaker_sample.wav -- a synthesized,
    two-speaker recording with a deliberate overlap and a deliberately
    short utterance (see data/audio/generate_test_fixture.py). See
    docs/adr/0012 for the measured accuracy this produced.
    """
    settings = get_settings()
    app.dependency_overrides[get_cached_embedding_provider] = FakeEmbeddingProvider
    app.dependency_overrides[get_cached_llm_provider] = lambda: FakeLLMProvider(
        structured_responses=[_EMPTY_EXTRACTION]
    )
    app.dependency_overrides[get_cached_transcription_provider] = lambda: (
        FasterWhisperTranscriptionProvider(model_name=settings.whisper_model)
    )
    app.dependency_overrides[get_cached_diarization_provider] = lambda: PyannoteDiarizationProvider(
        hf_token=settings.hf_token, model_name=settings.diarization_model
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", timeout=180.0
        ) as client:
            with _FIXTURE_WAV.open("rb") as file_handle:
                response = await client.post(
                    "/meetings/ingest-audio",
                    files={"file": ("2026-01-14_two-speaker-sample.wav", file_handle, "audio/wav")},
                )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] >= 8

    async with async_session_factory() as session:
        fetched = await MeetingRepository(session).get_by_id(body["meeting_id"])
    assert fetched is not None

    full_text = " ".join(chunk.text.lower() for chunk in fetched.chunks)
    for keyword in ["morning", "budget", "tuesday", "plan"]:
        assert keyword in full_text, f"expected {keyword!r} in transcribed text: {full_text!r}"

    distinct_speakers = {chunk.speaker for chunk in fetched.chunks}
    # At least two real speaker labels -- diarization actually distinguished
    # the two voices, not one undifferentiated blob. Not asserting an exact
    # count or that UNKNOWN_SPEAKER_LABEL appears: see docs/adr/0012 for why
    # this specific recording's constructed edge cases were resolved by the
    # majority-overlap rule rather than the unknown-speaker rule in practice.
    assert len(distinct_speakers - {UNKNOWN_SPEAKER_LABEL}) >= 2

    assert all(chunk.embedding is not None for chunk in fetched.chunks)
    assert all(
        isinstance(chunk.start_ts, int) and isinstance(chunk.end_ts, int)
        for chunk in fetched.chunks
    )
