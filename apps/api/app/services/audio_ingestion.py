"""Audio-to-transcript ingestion: decode -> transcribe + diarize (run
concurrently, since each is independent CPU-bound work over the same
waveform) -> align -> feed into the existing Phase 2 ingestion pipeline.
See docs/adr/0012.
"""

import asyncio
from io import BytesIO

import numpy as np
import soundfile as sf
from numpy.typing import NDArray
from scipy.signal import resample_poly
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Meeting
from app.providers.diarization.base import DiarizationProvider
from app.providers.embedding.base import EmbeddingProvider
from app.providers.transcription.base import TranscriptionProvider
from app.services.audio_alignment import align_transcript_and_diarization
from app.services.ingestion import ingest_audio_transcript

TARGET_SAMPLE_RATE = 16_000


def decode_audio_to_16k_mono(audio_bytes: bytes) -> NDArray[np.float32]:
    """Decode a WAV/FLAC file's raw bytes into a mono float32 waveform at
    TARGET_SAMPLE_RATE, ready for both TranscriptionProvider and
    DiarizationProvider -- decoded once here and shared between both,
    rather than each provider decoding the file itself.

    Deliberately uses soundfile (libsndfile) rather than ffmpeg-backed
    decoding: it handles WAV/FLAC natively with no system-level ffmpeg
    dependency, which keeps this feature's deployment footprint narrow.
    Compressed formats (mp3/m4a) are a known, documented gap -- see
    docs/adr/0012.
    """
    # soundfile ships no type stubs, so sf.read()'s return is Any to mypy --
    # np.asarray at each reassignment (and the final return) gives it back
    # an actual dtype instead of silently propagating Any throughout.
    try:
        raw_data, sample_rate = sf.read(BytesIO(audio_bytes), dtype="float32", always_2d=False)
    except sf.LibsndfileError as exc:
        raise ValueError(f"Could not decode audio file: {exc}") from exc
    data: NDArray[np.float32] = np.asarray(raw_data, dtype=np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1).astype(np.float32)
    if sample_rate != TARGET_SAMPLE_RATE:
        data = np.asarray(resample_poly(data, TARGET_SAMPLE_RATE, sample_rate), dtype=np.float32)
    return data


async def ingest_audio(
    *,
    filename: str,
    audio_bytes: bytes,
    transcription_provider: TranscriptionProvider,
    diarization_provider: DiarizationProvider,
    embedding_provider: EmbeddingProvider,
    session: AsyncSession,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> Meeting:
    """Transcribe and diarize an audio file, align the two into
    speaker-labelled turns, and ingest exactly like a text transcript. See
    docs/adr/0012 for the alignment policy and its edge-case handling.
    """
    waveform = decode_audio_to_16k_mono(audio_bytes)

    transcription_segments, diarization_segments = await asyncio.gather(
        transcription_provider.transcribe(waveform, sample_rate=TARGET_SAMPLE_RATE),
        diarization_provider.diarize(
            waveform,
            sample_rate=TARGET_SAMPLE_RATE,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        ),
    )
    turns = align_transcript_and_diarization(transcription_segments, diarization_segments)

    return await ingest_audio_transcript(
        filename=filename,
        turns=turns,
        embedding_provider=embedding_provider,
        session=session,
    )
