from io import BytesIO

import numpy as np
import soundfile as sf

from app.services.audio_ingestion import TARGET_SAMPLE_RATE, decode_audio_to_16k_mono


def _wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    buffer = BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV")
    return buffer.getvalue()


def test_decode_resamples_to_the_target_rate() -> None:
    original_rate = 22_050
    samples = np.zeros(original_rate, dtype=np.float32)  # 1 second of silence

    waveform = decode_audio_to_16k_mono(_wav_bytes(samples, original_rate))

    assert waveform.dtype == np.float32
    # Resampled from 1s @ 22050Hz to TARGET_SAMPLE_RATE -- same duration,
    # a different sample count.
    assert abs(len(waveform) - TARGET_SAMPLE_RATE) <= 1


def test_decode_leaves_already_16k_audio_untouched_in_length() -> None:
    samples = np.zeros(TARGET_SAMPLE_RATE, dtype=np.float32)

    waveform = decode_audio_to_16k_mono(_wav_bytes(samples, TARGET_SAMPLE_RATE))

    assert len(waveform) == TARGET_SAMPLE_RATE


def test_decode_downmixes_stereo_to_mono() -> None:
    left = np.full(TARGET_SAMPLE_RATE, 0.5, dtype=np.float32)
    right = np.full(TARGET_SAMPLE_RATE, -0.5, dtype=np.float32)
    stereo = np.stack([left, right], axis=1)

    waveform = decode_audio_to_16k_mono(_wav_bytes(stereo, TARGET_SAMPLE_RATE))

    assert waveform.ndim == 1
    # Average of +0.5 and -0.5 is 0.0.
    assert np.allclose(waveform, 0.0, atol=1e-3)
