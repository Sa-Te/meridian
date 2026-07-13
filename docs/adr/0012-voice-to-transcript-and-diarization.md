# ADR-0012: Voice-to-transcript ingestion with real speaker diarization

Status: Accepted
Date: 2026-07-13

## Context

ROADMAP Phase 10 (deferred until after Phase 9's testing/CI hardening
landed, per CLAUDE.md Section 9 -- see ADR-0015/0016) asks for a real
audio ingestion path: transcription, genuine speaker diarization (not
transcription-only, not hardcoded labels), realistic edge-case handling,
and an honest accuracy report against a real test recording. The explicit
brief was to feed the result into the existing Phase 2 pipeline
"unchanged" -- parse -> chunk -> embed -> store, with extraction,
guardrails, and tracing all applying automatically.

## Decision

**Transcription: faster-whisper, local, CPU.** `app/providers/transcription/`
follows the exact ports-and-adapters shape ADR-0002/0004 established for
`EmbeddingProvider`/`LLMProvider`: a `TranscriptionProvider` ABC (one
method, `transcribe(waveform, sample_rate) -> list[TranscriptionSegment]`,
each segment carrying real sub-second start/end times) and one concrete
implementation, `FasterWhisperTranscriptionProvider`, wrapping a
`faster-whisper` `WhisperModel("small", device="cpu", compute_type="int8")`
via `asyncio.to_thread` -- the identical lazy-load-once pattern
`LocalBGEEmbeddingProvider` already uses. No external API key, consistent
with keeping `GEMINI_API_KEY` the only *required* key for the system's
core functionality.

**Diarization: pyannote.audio's pretrained pipeline.**
`app/providers/diarization/` mirrors the same shape:
`DiarizationProvider.diarize(waveform, sample_rate, min_speakers=,
max_speakers=) -> list[DiarizationSegment]`, and
`PyannoteDiarizationProvider` wraps `Pipeline.from_pretrained(
"pyannote/speaker-diarization-3.1", token=HF_TOKEN)`. This is the one
place in the whole system that requires an external dependency beyond
`GEMINI_API_KEY`: a free HuggingFace account, the gated model terms
accepted on two model pages, and a read-scoped access token
(`HF_TOKEN`, optional, only required for this feature -- same pattern as
`VOYAGE_API_KEY`). Accepted because it's a one-time, free setup step, not
a recurring cost, and because the assignment explicitly wants real
diarization -- an ungated, hand-rolled embedding-clustering pipeline was
the fallback plan (see Alternatives) if that setup proved impractical; it
didn't.

`min_speakers`/`max_speakers` are exposed as optional query parameters on
`POST /meetings/ingest-audio`, passed straight through to the pipeline --
a caller who already knows roughly how many speakers to expect can narrow
the search; omitted, the pipeline auto-detects.

**Alignment: majority-overlap-duration voting with two escape hatches to
"unknown."** `app/services/audio_alignment.py`'s
`align_transcript_and_diarization` is the actual novel logic this phase
adds. For each transcription segment, it computes total overlap duration
against every diarization segment, and applies four rules in order:

1. **Short utterance** (`duration < 0.5s`, `min_segment_duration_seconds`):
   labelled `"Unknown Speaker"` regardless of overlap -- too little signal
   to attribute confidently. This is the ROADMAP's own named example.
2. **No overlap**: no diarization segment covers any part of the
   transcription segment at all -> `"Unknown Speaker"`.
3. **No clear majority** (`best_speaker_fraction < 0.5`,
   `min_overlap_fraction`): even the best-covering speaker accounts for
   less than half the segment -> `"Unknown Speaker"` rather than a guess.
4. **Contested overlap**: the runner-up speaker is within 0.2
   (`overlap_contest_margin`) of the winner's share, and the runner-up
   itself clears 0.3 (`overlap_contest_floor`) -> `"Unknown Speaker"`.
   This is what genuine overlapping/cross-talk speech looks like in the
   overlap-duration data -- two speakers each covering a substantial,
   similar share of one segment -- and picking either one over the other
   would be a coin flip dressed up as a finding.

A segment that clears all four passes gets the winning speaker's raw
label (e.g. `"SPEAKER_00"`) remapped to a stable `"Speaker N"`, assigned
in first-appearance order across the whole recording -- readable, but
making no claim about real identity, since none is available from audio
alone.

**Speaker-count mismatch (more or fewer diarized speakers than the true
count) is handled by not hiding it.** No code here tries to detect or
correct an over- or under-segmented diarization pass -- there is no
ground truth available at ingestion time to compare against. If
diarization reports 3 speakers for a 2-person conversation, the output
shows 3 distinct `"Speaker N"` labels; if it collapses 2 speakers into 1,
the output shows 1. Both are reported honestly, not silently merged or
split. The one real lever available is the `min_speakers`/`max_speakers`
hint above, for a caller who has prior knowledge.

**Reusing Phase 2 "unchanged," precisely defined.** The ROADMAP asked for
the aligned transcript to feed into the existing `parse -> chunk -> embed
-> store` pipeline unchanged. `app/services/ingestion.py`'s
`ingest_transcript` was split into a shared `_ingest_turns` core (chunk ->
embed -> store, taking `list[SpeakerTurn]` directly) plus a thin
`parse_transcript`-calling wrapper; a new `ingest_audio_transcript` calls
the *same* `_ingest_turns` core with the aligned turns from
`audio_alignment.py`. Deliberately **not** implemented as: format the
aligned turns into `"[HH:MM:SS] Speaker: text"` raw text and feed that
through the *original*, fully unmodified `ingest_transcript` function.
That would have meant zero lines changed in `ingestion.py`, but it would
silently discard real information: `parse_transcript`'s text format
carries only one timestamp per turn and reconstructs `end_ts` as "the next
turn's `start_ts`" (see `SpeakerTurn`'s docstring) -- a reasonable
approximation for a format that never had real end timestamps to begin
with, but a real, avoidable accuracy loss for audio, which has a genuine
per-segment end time from Whisper. `chunk_turns` (the actual "chunk" step)
and every downstream stage -- embedding, extraction, guardrails, tracing
-- run completely unmodified either way; only the parse-vs-align entry
point differs, and only because audio's "parse" step naturally produces
`SpeakerTurn` objects directly rather than text to be re-parsed.
`Meeting.raw_text` is still populated for audio meetings, via
`_serialize_turns`, for display and idempotent re-ingest lookups -- it's
just never re-parsed.

**Tracing** (ADR-0010) follows the exact `ingest_meeting` pattern:
`TracingTranscriptionProvider`/`TracingDiarizationProvider` decorators
(new, alongside the existing `TracingEmbeddingProvider`/
`TracingLLMProvider`) record `"transcribe"`/`"diarize"` stages
automatically; the router wraps an explicit `"ingest_audio"` stage around
decode+transcribe+diarize+align, then calls a new shared `_finish_ingest`
helper (extracted from `ingest_meeting`'s body, now used by both
endpoints) for the prompt-injection-scan -> extract -> persist -> response
sequence that was previously duplicated between what would otherwise be
two near-identical endpoint functions.

## Alternatives considered

- **API-based Whisper (e.g. a hosted transcription API) instead of
  faster-whisper.** Rejected as the default: it would add a second
  required external API key for a feature that doesn't need one --
  faster-whisper's CPU performance on short-to-medium recordings (the
  30-second test fixture transcribed in under 5 seconds once the model was
  loaded) is more than adequate for this project's scale, and it keeps the
  "only `GEMINI_API_KEY` is required for the core system" story true for
  the base text pipeline. `TranscriptionProvider`'s interface exists
  specifically so an API-based provider is a config swap later, not a
  rewrite, if throughput or accuracy needs ever outgrow a local model.
- **A hand-rolled, ungated diarization pipeline (speaker-embedding
  extraction + clustering, e.g. via speechbrain's ECAPA-TDNN) instead of
  pyannote.audio.** This was the concrete fallback plan specifically to
  avoid the HF gating friction below. Not needed in the end -- the gating
  process (accept two, then a third, unexpected, model license) took a
  few minutes, not a blocking delay -- but it remains the documented
  escape hatch if `HF_TOKEN` provisioning is ever impractical in some
  deployment context. It would trade pyannote's pretrained, SOTA
  segmentation+clustering pipeline for meaningfully more hand-written
  ML code and, almost certainly, lower out-of-box accuracy.
- **Silently "fixing" a wrong speaker count** (forcing diarization output
  to match an assumed number of speakers) instead of reporting it as-is.
  Rejected: there's no reliable ground truth to fix *toward* at ingestion
  time, and pretending certainty that isn't there is worse than an honest,
  visibly-off speaker count a human reviewing the transcript can correct.
- **Picking the higher-overlap speaker whenever there's any overlap at
  all**, instead of the contested-overlap rule (Rule 4). Rejected:
  overlapping speech is exactly the case where "pick whoever has slightly
  more" is least trustworthy -- see the real measured case below, where a
  55/45 split was *not* contested (correctly, since the margin was still
  decisive there) but a near-even split in testing was.

## Consequences: what this actually measured

Real numbers from `tests/integration/test_ingest_audio.py`'s one
real-pipeline test, run against
`data/audio/test_multi_speaker_sample.wav` -- a 30-second, two-speaker
recording synthesized with `espeak-ng` TTS (see
`data/audio/generate_test_fixture.py`), containing 10 turns, one
deliberately constructed overlapping-speech moment, and one deliberately
short utterance ("Okay."). **This is not a claim that the pipeline is
flawless** -- it's a report of exactly what one real run produced,
including where it didn't behave as originally expected:

- **Transcription**: 9 of 10 turns transcribed essentially verbatim.
  One genuine ASR error: "The budget came in under projections this
  quarter" came back as "...projections, DisqWarger" -- a real
  mis-transcription, not cherry-picked away. faster-whisper's `small`
  model took under 5 seconds to transcribe the 30-second clip on CPU
  after the model was loaded (loading itself takes longer on a cold
  cache).
- **Diarization**: correctly identified exactly two distinct speakers
  across the whole recording, and genuinely detected the constructed
  overlap as an overlapping segment in its own output (two speakers with
  real, overlapping time ranges around the 18-20 second mark) --
  confirming `PyannoteDiarizationProvider` reads `.speaker_diarization`
  (overlap-preserving), not `.exclusive_speaker_diarization`, correctly.
- **Alignment on the constructed overlap**: did *not* trigger Rule 4. The
  dominant speaker covered roughly 96% of the transcription segment's
  duration; the brief real overlap from the second speaker covered
  roughly 37% of that same window. A 59-point margin is decisively past
  the 20-point contest threshold, so this correctly resolved to "one
  speaker dominates, with some genuine bleed-over at the edge" rather
  than "these two are both talking" -- the same distinction
  `test_two_speakers_above_contest_floor_but_far_apart_is_not_contested`
  (one of 15 unit tests exercising every rule against hand-constructed,
  exact timings) verifies deterministically. The construction that *does*
  reliably trigger Rule 4 needs the two speakers' shares closer to even,
  as that unit test suite's dedicated contested-overlap case shows.
- **Alignment on the short utterance**: also did *not* trigger Rule 1, and
  this is the most useful honest finding here. The underlying "Okay."
  clip is genuinely 0.39 seconds of audio (confirmed against the
  fixture's own ground-truth ground truth JSON). faster-whisper's own
  reported segment boundary for it, however, came back as exactly 0.50
  seconds -- landing precisely on, not under, the configured threshold.
  This says something real about calibrating this kind of rule: the
  threshold has to be checked against what the ASR model *reports* as a
  segment's duration, not the true acoustic event duration, since the two
  aren't identical (Whisper's segmentation has its own rounding/framing
  granularity). The rule's correctness at any given threshold is proven
  by the unit tests, not by this one recording happening to cross it.
- **End-to-end**: the resulting `Meeting`/`Chunk` rows are structurally
  identical to a text-ingested meeting -- same fields, same types,
  `embedding` populated, `start_ts`/`end_ts` as whole-second integers --
  verified directly in the integration test.

## Consequences: real dependency friction hit along the way

Worth recording since it shaped several decisions above:

- **pyannote.audio's current release (4.0.7) redirected
  `pyannote/speaker-diarization-3.1` through a second, different gated
  repo** (`pyannote/speaker-diarization-community-1`) the first two
  accepted model licenses didn't cover. Resolved by accepting that
  third page too, not by downgrading pyannote.audio -- the 3.x line
  turned out to be incompatible with this environment's current
  `torchaudio` (a removed `AudioMetaData` attribute) and current
  `huggingface_hub` (a removed `use_auth_token` parameter in
  `hf_hub_download`), neither of which could be downgraded without
  breaking `transformers`' own `huggingface_hub>=1.5.0` floor -- i.e.
  breaking the existing embedding pipeline to accommodate the audio one.
  Staying on current pyannote.audio and asking for one more gated-model
  acceptance was the smaller, more contained change.
- **pyannote 4.x's pipeline call returns a `DiarizeOutput` dataclass, not
  a bare `Annotation`** -- `.speaker_diarization` (overlap-preserving) is
  what this project reads; `.exclusive_speaker_diarization` (overlap
  removed) exists but would have silently defeated Rule 4 entirely.
- **`sentence-transformers` 5.x imports `torchcodec` unconditionally at
  module load time** (for an unrelated, unused audio/video embedding
  feature), which hard-crashes in this environment (no working ffmpeg).
  Since `torchcodec` only entered the dependency graph *because*
  `pyannote.audio` needs it, adding the audio feature broke the
  already-working local BGE embedding path -- a real instance of an
  optional feature's transitive dependency breaking an unrelated, core
  one. Fixed by pinning `sentence-transformers<5.0` in
  `apps/api/pyproject.toml` (no real feature loss: this project only ever
  used its text-embedding model).
- **Docker CPU-only torch**: the Dockerfile's existing
  `pip install torch --index-url .../whl/cpu` pre-install step needs the
  same `--extra-index-url` applied to the main dependency install too,
  or `pip` resolves pyannote.audio's own `torch`/`torchaudio` requirement
  from the default (CUDA) index and silently replaces the CPU build.

## Links

- ADR-0002 (core tech stack; the ports-and-adapters pattern this extends)
- ADR-0004 (embedding provider; `LocalBGEEmbeddingProvider`'s
  lazy-load-once pattern this reuses)
- ADR-0006 (chunking strategy; the `start_ts`/`end_ts` assumptions this
  ADR's "reusing Phase 2 unchanged" section addresses directly)
- ADR-0010 (observability/tracing; the decorator pattern extended here)
- ADR-0015/0016 (why Phase 10 waited on Phase 9's hardening first)
- `app/providers/transcription/`, `app/providers/diarization/`
- `app/services/audio_alignment.py`, `app/services/audio_ingestion.py`
- `app/services/ingestion.py` (`_ingest_turns`, `ingest_audio_transcript`)
- `app/routers/meetings.py` (`ingest_audio_meeting`, `_finish_ingest`)
- `data/audio/generate_test_fixture.py`,
  `tests/integration/test_ingest_audio.py`,
  `tests/unit/test_audio_alignment.py`
