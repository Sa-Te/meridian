"""Generates data/audio/test_multi_speaker_sample.wav and its ground-truth
sidecar test_multi_speaker_sample.json, used by
apps/api/tests/integration/test_ingest_audio.py. See docs/adr/0012.

Not run automatically -- this is a one-off generation script, not a test.
The generated .wav/.json ARE checked into the repo; ./_raw_clips/ (the raw
per-utterance TTS clips this script mixes together) is not -- it's a
regenerable intermediate, gitignored, not needed to run anything.

To regenerate from scratch (espeak-ng isn't a project dependency -- only
needed to rebuild this fixture, not to run the system; run it in a
throwaway container if you don't have it installed locally):

    mkdir -p data/audio/_raw_clips
    cd data/audio/_raw_clips
    espeak-ng -v en-us    -s 165 -w a1.wav "Good morning everyone, thanks for joining the call today."
    espeak-ng -v en-us+f3 -s 165 -w b1.wav "Sure, happy to be here."
    espeak-ng -v en-us    -s 165 -w a2.wav "Let's start with the budget update from last week."
    espeak-ng -v en-us+f3 -s 165 -w b2.wav "The budget came in under projections this quarter."
    espeak-ng -v en-us    -s 165 -w a3.wav "That sounds reasonable to me."
    espeak-ng -v en-us+f3 -s 165 -w b3.wav "I agree, we should move forward with the plan."
    espeak-ng -v en-us    -s 165 -w a_overlap.wav "Right, right."
    espeak-ng -v en-us    -s 260 -w a4.wav "Okay."
    espeak-ng -v en-us+f3 -s 165 -w b4.wav "Can we lock in a date for the rollout?"
    espeak-ng -v en-us    -s 165 -w a5.wav "Let's say next Tuesday, does that work?"
    espeak-ng -v en-us+f3 -s 165 -w b5.wav "Yes, Tuesday works well for me."
    cd ../../..
    python3 data/audio/generate_test_fixture.py

a4.wav ("Okay.") is deliberately spoken faster (-s 260 vs. 165 elsewhere)
to keep its true spoken duration comfortably under the alignment policy's
0.5s short-utterance threshold -- see docs/adr/0012's honest note on where
this landed in practice (faster-whisper's own segment-boundary reporting
has its own granularity, which mattered more than expected here).
"""

import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SAMPLE_RATE = 16_000
SILENCE_SECONDS = 0.6
CLIPS_DIR = Path(__file__).parent / "_raw_clips"
OUTPUT_WAV = Path(__file__).parent / "test_multi_speaker_sample.wav"
OUTPUT_JSON = Path(__file__).parent / "test_multi_speaker_sample.json"


def _load_16k_mono(path: Path) -> np.ndarray:
    data, sample_rate = sf.read(path, dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sample_rate != SAMPLE_RATE:
        data = resample_poly(data, SAMPLE_RATE, sample_rate).astype(np.float32)
    return data


def main() -> None:
    silence = np.zeros(int(SILENCE_SECONDS * SAMPLE_RATE), dtype=np.float32)

    turns = [
        ("Speaker A", "a1.wav", "Good morning everyone, thanks for joining the call today."),
        ("Speaker B", "b1.wav", "Sure, happy to be here."),
        ("Speaker A", "a2.wav", "Let's start with the budget update from last week."),
        ("Speaker B", "b2.wav", "The budget came in under projections this quarter."),
        ("Speaker A", "a3.wav", "That sounds reasonable to me."),
        # b3 gets overlapped near its tail end by a_overlap ("Right, right.") --
        # the one deliberately-constructed genuine-overlap moment.
        ("Speaker B", "b3.wav", "I agree, we should move forward with the plan."),
        # a4 ("Okay.") is the deliberately short, isolated utterance.
        ("Speaker A", "a4.wav", "Okay."),
        ("Speaker B", "b4.wav", "Can we lock in a date for the rollout?"),
        ("Speaker A", "a5.wav", "Let's say next Tuesday, does that work?"),
        ("Speaker B", "b5.wav", "Yes, Tuesday works well for me."),
    ]

    timeline = np.zeros(0, dtype=np.float32)
    ground_truth = []
    overlap_clip = _load_16k_mono(CLIPS_DIR / "a_overlap.wav")
    overlap_fraction_into_tail = 0.6  # overlay starts 60% of the way through b3

    for speaker, clip_name, text in turns:
        clip = _load_16k_mono(CLIPS_DIR / clip_name)
        start_sample = len(timeline)
        timeline = np.concatenate([timeline, clip])

        if clip_name == "b3.wav":
            overlay_start = start_sample + int(len(clip) * overlap_fraction_into_tail)
            overlay_end = overlay_start + len(overlap_clip)
            if overlay_end > len(timeline):
                timeline = np.concatenate(
                    [timeline, np.zeros(overlay_end - len(timeline), dtype=np.float32)]
                )
            timeline[overlay_start:overlay_end] += overlap_clip
            ground_truth.append(
                {
                    "speaker": "Speaker A",
                    "text": "Right, right.",
                    "start_sec": round(overlay_start / SAMPLE_RATE, 2),
                    "end_sec": round(overlay_end / SAMPLE_RATE, 2),
                    "is_overlap": True,
                }
            )

        end_sample = start_sample + len(clip)
        ground_truth.append(
            {
                "speaker": speaker,
                "text": text,
                "start_sec": round(start_sample / SAMPLE_RATE, 2),
                "end_sec": round(end_sample / SAMPLE_RATE, 2),
                "is_short_utterance": clip_name == "a4.wav",
            }
        )

        timeline = np.concatenate([timeline, silence])

    peak = np.abs(timeline).max()
    if peak > 1.0:
        timeline = timeline / peak * 0.98

    sf.write(OUTPUT_WAV, timeline, SAMPLE_RATE)
    OUTPUT_JSON.write_text(json.dumps({"turns": ground_truth}, indent=2))
    print(f"Wrote {OUTPUT_WAV} ({len(timeline) / SAMPLE_RATE:.1f}s) and {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
