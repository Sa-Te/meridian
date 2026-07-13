from unittest.mock import MagicMock

import numpy as np
import pytest

from app.providers.diarization.pyannote_provider import PyannoteDiarizationProvider


class _FakeTurn:
    def __init__(self, start: float, end: float) -> None:
        self.start = start
        self.end = end


def _fake_diarize_output(tracks: list[tuple[float, float, str]]) -> MagicMock:
    """Mocks pyannote 4.x's DiarizeOutput -- .speaker_diarization is the
    Annotation with overlapping turns intact, which is what
    PyannoteDiarizationProvider actually reads."""
    annotation = MagicMock()
    annotation.itertracks.return_value = [
        (_FakeTurn(start, end), None, speaker) for start, end, speaker in tracks
    ]
    output = MagicMock()
    output.speaker_diarization = annotation
    return output


def _provider() -> PyannoteDiarizationProvider:
    return PyannoteDiarizationProvider(hf_token="fake-token")


async def test_diarize_maps_tracks_in_order() -> None:
    provider = _provider()
    fake_pipeline = MagicMock(
        return_value=_fake_diarize_output([(0.0, 2.1, "SPEAKER_00"), (2.1, 4.0, "SPEAKER_01")])
    )
    provider._pipeline = fake_pipeline

    result = await provider.diarize(np.zeros(16_000, dtype=np.float32), sample_rate=16_000)

    assert [segment.speaker_label for segment in result] == ["SPEAKER_00", "SPEAKER_01"]
    assert result[0].start_ts == 0.0
    assert result[0].end_ts == 2.1
    call_args = fake_pipeline.call_args
    assert call_args.args[0]["sample_rate"] == 16_000
    assert "min_speakers" not in call_args.kwargs
    assert "max_speakers" not in call_args.kwargs


async def test_diarize_passes_speaker_count_hints_when_given() -> None:
    provider = _provider()
    fake_pipeline = MagicMock(return_value=_fake_diarize_output([]))
    provider._pipeline = fake_pipeline

    await provider.diarize(
        np.zeros(16_000, dtype=np.float32), sample_rate=16_000, min_speakers=2, max_speakers=4
    )

    assert fake_pipeline.call_args.kwargs == {"min_speakers": 2, "max_speakers": 4}


async def test_pipeline_is_loaded_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pipeline = MagicMock(return_value=_fake_diarize_output([]))
    fake_from_pretrained = MagicMock(return_value=fake_pipeline)
    monkeypatch.setattr(
        "app.providers.diarization.pyannote_provider.Pipeline.from_pretrained",
        fake_from_pretrained,
    )
    provider = _provider()

    await provider.diarize(np.zeros(16_000, dtype=np.float32), sample_rate=16_000)
    await provider.diarize(np.zeros(16_000, dtype=np.float32), sample_rate=16_000)

    fake_from_pretrained.assert_called_once_with(
        "pyannote/speaker-diarization-3.1", token="fake-token"
    )


async def test_raises_a_clear_error_when_pipeline_fails_to_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.providers.diarization.pyannote_provider.Pipeline.from_pretrained",
        MagicMock(return_value=None),
    )
    provider = _provider()

    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        await provider.diarize(np.zeros(16_000, dtype=np.float32), sample_rate=16_000)
