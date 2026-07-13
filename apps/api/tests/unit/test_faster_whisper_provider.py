from dataclasses import dataclass
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.providers.transcription.faster_whisper_provider import FasterWhisperTranscriptionProvider


@dataclass
class _FakeSegment:
    start: float
    end: float
    text: str


def _provider() -> FasterWhisperTranscriptionProvider:
    return FasterWhisperTranscriptionProvider()


async def test_transcribe_maps_segments_in_order() -> None:
    provider = _provider()
    fake_model = MagicMock()
    fake_model.transcribe.return_value = (
        [
            _FakeSegment(start=0.0, end=1.5, text=" Hello there."),
            _FakeSegment(start=1.5, end=3.2, text=" How are you?"),
        ],
        MagicMock(),
    )
    provider._model = fake_model

    result = await provider.transcribe(np.zeros(16_000, dtype=np.float32), sample_rate=16_000)

    assert [segment.text for segment in result] == ["Hello there.", "How are you?"]
    assert result[0].start_ts == 0.0
    assert result[0].end_ts == 1.5
    fake_model.transcribe.assert_called_once()
    assert fake_model.transcribe.call_args.kwargs["language"] == "en"


async def test_transcribe_rejects_non_16k_audio() -> None:
    provider = _provider()
    provider._model = MagicMock()

    with pytest.raises(ValueError, match="16000Hz"):
        await provider.transcribe(np.zeros(8_000, dtype=np.float32), sample_rate=8_000)


async def test_model_is_loaded_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_model = MagicMock()
    fake_model.transcribe.return_value = ([], MagicMock())
    fake_constructor = MagicMock(return_value=fake_model)
    monkeypatch.setattr(
        "app.providers.transcription.faster_whisper_provider.WhisperModel", fake_constructor
    )
    provider = _provider()

    await provider.transcribe(np.zeros(16_000, dtype=np.float32), sample_rate=16_000)
    await provider.transcribe(np.zeros(16_000, dtype=np.float32), sample_rate=16_000)

    fake_constructor.assert_called_once_with("small", device="cpu", compute_type="int8")
