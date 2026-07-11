# ADR-0009: Evaluation methodology

Status: Accepted
Date: 2026-07-11

## Context

Phase 5 is the "Quality Controls" and "AI Evaluation & Observability"
assignment checkpoint. Everything built in Phases 2-4 -- chunking, hybrid
retrieval, citation-enforced generation, structured extraction, guardrails
-- was tuned by reasoning rather than measurement. ADR-0007 says this
directly about `top_k` and the fusion weights, and ADR-0008 says the same
about both confidence thresholds: each names Phase 5's eval harness as "the
intended mechanism for tuning ... with real evidence instead of intuition."
This phase is that mechanism, and it needs to produce a real, CI-enforced
quality gate, not a report nobody reads.

Two design questions had to be settled before any code: what to measure, and
against what ground truth.

## Decision

### Metric set: retrieval hit-rate + LLM-as-judge faithfulness/relevance

Two families of signal, computed per golden question and then aggregated:

- **Retrieval**: `precision@k` and `recall@k` (`eval/metrics.py`), scored
  against the question's expected supporting chunk(s), using the real
  `hybrid_search` call (`app/services/retrieval.py`) with the app's actual
  configured `top_k`/weights/pool size -- not a synthetic retrieval stand-in.
- **Answer quality**: an LLM-judge call (`eval/judge.py`) scores
  **faithfulness** (does every claim in the answer trace back to the cited
  excerpts) and **relevance** (does the answer actually address the
  question, given what was retrieved), both 1-5.

Both are necessary. Retrieval metrics alone can't catch a generation bug
that produces a fluent, wrong answer from perfectly good retrieved context
-- and answer-quality metrics alone can't distinguish "the retriever failed"
from "the retriever succeeded and the model still got it wrong." Measuring
only one half would leave the other half's regressions invisible to CI.

### Why LLM-as-judge instead of only retrieval metrics

Retrieval metrics are cheap, deterministic, and fully explainable, but they
say nothing about the generation step -- whether the model actually used
what it was given correctly, or embellished beyond it despite passing the
citation guardrail (which only checks that a cited `chunk_id` was really
retrieved, not that every clause in the prose is actually grounded in it).
A held-out human-graded rubric would be the gold standard, but hand-grading
20 answers on every CI run isn't viable, and this project has no annotator
pool. An LLM-judge is the practical middle ground: cheap enough to run in
CI, and -- unlike a hand-rolled string-similarity metric against
`expected_answer` -- actually able to reason about whether a paraphrased,
differently-worded answer is nonetheless faithful and relevant.

**Gemini judges Gemini's own output.** Per ADR-0013, Gemini is the sole
active `LLMProvider` (the only path with a working `generate_structured`
implementation -- ADR-0008 -- which the judge needs for its own structured
`JudgeVerdict` output), so the same model that generates the answer being
judged also judges it. This is a real, acknowledged limitation:
self-preference bias is a documented failure mode of LLM-as-judge setups,
where a model rates its own family's outputs more favorably than an
independent judge would. It was accepted rather than worked around for this
submission -- see Consequences and the README's "what I'd do differently."

The judge call (`eval/judge.py:judge_answer`) is a separate, clearly-labelled
LLM call from the one that produced the answer: its own system prompt
(`JUDGE_SYSTEM_PROMPT`), its own schema (`JudgeVerdict`), and it is not shown
how the answer was produced -- only the question, the excerpts that were
available (each tagged `CITED`/`UNCITED`), and the final answer text. The
judge prompt explicitly instructs that an honest "not well-supported"
decline is fully faithful and fully relevant when the excerpts genuinely
don't answer the question -- without that instruction, a naive judge might
penalize a correct decline for "not answering," which would perversely
reward hallucination over honesty.

### Golden dataset: 20 questions, quote-anchored ground truth

`eval/golden_dataset/golden_questions.json` holds 20 hand-written entries:
6 direct-fact, 7 decision, 4 action-item, 3 deliberately out-of-scope
(covering all 12 seed transcripts). Each in-scope entry names
`source_meeting_filename` and one or more `expected_supporting_quotes` --
exact substrings copied from the transcript -- rather than a hardcoded
`chunk_index`.

This matters because chunking merges consecutive same-speaker turns
(`app/services/chunking.py`, ADR-0006) and chunk ids are random UUIDs
assigned at ingest time. A hand-computed index would require mentally
re-simulating the merge algorithm for every transcript and would silently
go stale the moment chunking logic changes. Quote-matching sidesteps both
problems: `eval/golden.py:resolve_expected_chunk_ids` finds whichever real,
freshly-ingested chunk the quote ends up inside of, whatever that chunk's
boundaries turn out to be. If a quote matches zero or more than one chunk,
it raises `GoldenDatasetError` loudly rather than guessing -- a stale or
ambiguous dataset entry is a bug to fix, not a value to average around.

**Recall is hit-rate, not fractional multi-document recall.** Calibrating
the harness against the real system (see Consequences) surfaced three
questions (`dec-2`, `dec-3`, `ai-4`) where the transcript states the same
decision or commitment in two different turns -- an initial proposal and a
later recap, say -- and the retriever correctly found and cited one while
missing the other. Both chunks are independently sufficient, equally
correct citations for the same single fact; they are not two different
facts that both need retrieving. Scoring `recall_at_k` fractionally (find
1 of 2 -> 0.5) would penalize the retriever for something that isn't a
retrieval quality problem. `recall_at_k` therefore returns 1.0 if *any*
expected chunk was retrieved, 0.0 otherwise -- see `eval/metrics.py`.
`precision_at_k` is unaffected: it's still the fraction of the retrieved
top-k that intersects the expected set, and crediting more than one
alternate chunk if both happen to be retrieved is still correct.

### Questions are asked globally, not scoped per-meeting

Golden questions are scored against `hybrid_search` with `meeting_id=None`
(the same retrieval a real `POST /ask` call across all meetings would run),
not scoped to their `source_meeting_filename`. A real user asking Meridian
a question doesn't necessarily know which of the twelve meetings holds the
answer -- global search is the actual product surface being evaluated.
`source_meeting_filename` is used only by the eval harness itself, to
resolve which chunk(s) the quote refers to; it is never passed to
retrieval. This is a harder, more realistic test than per-meeting scoping,
and it surfaced a genuine cross-meeting ambiguity during calibration (see
Consequences).

### CI gate: recall@k and faithfulness, not relevance or guardrail accuracy

`eval/run_eval.py` exits non-zero if mean `recall@k` or mean `faithfulness`
(across in-scope questions for the former, all questions for the latter)
falls below its threshold -- the two metrics ROADMAP.md Phase 5 explicitly
names as the CI-blocking pair. Mean `relevance` and an
`answered_as_expected_rate` (did `supported` match what the question's
category implies -- `True` for in-scope, `False` for out-of-scope) are
computed and written to the report, but not gated on: with only 3
out-of-scope questions, one misfire swings that rate by a third, too noisy
at this sample size to be a hard gate without either growing the
out-of-scope set substantially or accepting frequent false-positive CI
failures. Reported-but-not-gated is the honest middle ground -- visible to
a reviewer, not a source of flaky builds.

### Threshold values, calibrated against a real measured run

- **`RECALL_AT_K_THRESHOLD = 0.85`**
- **`FAITHFULNESS_THRESHOLD = 4.0`** (out of 5)

These were not guessed in the abstract -- they were set after running the
full harness for real (local Postgres + pgvector, the real local BGE
embedding model, the real Gemini API) and reading the result. That run
scored mean `recall@k = 0.941` (16 of 17 in-scope questions) and mean
`faithfulness = 5.000`. The one miss, `df-2` ("how much did onboarding
completion drop"), is a genuine, honestly-kept retrieval gap: the actual
figure ("Sixty-one percent to forty-four percent...") lives in a chunk that
is a bare number with no restated context, one turn after the question that
gives it meaning ("Dropped how much?") and two turns after the topic-setting
statement ("Completion rate dropped."). Speaker-turn chunking (ADR-0006)
keeps each of those three alternating-speaker turns as a separate chunk, so
the numeric-answer chunk embeds and full-text-matches poorly against a
question phrased around "onboarding completion drop" -- the words that
actually describe the number live in a neighboring chunk, not the one
holding the number itself. This was left in the golden dataset deliberately
rather than swapped for an easier question: it's real, measured signal
about a real limitation, and hiding it would defeat the purpose of building
an eval harness in the first place.

`0.85` leaves headroom for roughly one additional miss beyond the measured
baseline (15/17 = 0.882 still clears it; 14/17 = 0.824 would not) --
protection against embedding-model or fusion-weight noise across runs,
while still failing on a real regression (e.g. someone drops `top_k` to 2,
or breaks fusion scoring). `4.0` sits meaningfully below the measured
`5.000` for the same reason: citation enforcement (ADR-0007/0008)
mechanically blocks the model from citing an unretrieved chunk, so
faithfulness is expected to run high; the gap to `5.0` is room for the
model to editorialize a little beyond its citations before the gate
actually trips.

### Idempotent local runs; rate-limited real API calls

`eval/run_eval.py` ingests every transcript under `data/transcripts/` via
the real `ingest_transcript` pipeline (Phase 2), reusing an already-ingested
`Meeting` by `source_filename`
(`MeetingRepository.get_by_source_filename`, added this phase) rather than
re-ingesting one a prior local run already created -- otherwise every local
re-run against a persistent dev database would pile up duplicate meetings.
CI's ephemeral Postgres service doesn't need this, but a developer running
`python -m eval.run_eval` repeatedly against `docker compose`'s Postgres
does.

Free-tier Gemini keys cap `generate_content` at 15 requests/minute. This
script makes two real LLM calls per in-scope question (generation, then the
separate judge call) back-to-back -- unlike normal request traffic, which
CI's own quota headroom was designed around. `eval/run_eval.py` paces those
calls with a fixed 4.5s minimum interval (`_LLMRateLimiter`) to stay under
the cap proactively, backed by a retry-with-exponential-backoff wrapper
(`_with_retry`) as a backstop for the rare transient 429/5xx pacing alone
doesn't prevent. This was found, not assumed: an early real run without
pacing hit `429 RESOURCE_EXHAUSTED` mid-run.

## Alternatives considered

- **Hardcoded `chunk_index` per golden question**, as the ROADMAP's
  "expected-supporting-chunk-id" wording might suggest literally. Rejected
  -- see "Golden dataset" above; fragile against both re-ingestion (new
  random UUIDs) and any future chunking change (different merge
  boundaries), and unreadable to a reviewer without cross-referencing the
  transcript by hand. A quoted substring is self-documenting: a reviewer
  can see directly, in the dataset file, why that's the right answer.
- **Fractional `recall@k`** (relevant retrieved / all expected). Rejected
  once real calibration showed it punishes the retriever for not finding
  every restatement of one already-found fact -- see "Recall is hit-rate"
  above.
- **Scoping golden questions to their source meeting** (`meeting_id` set)
  instead of global search. Rejected: it tests a narrower, easier retrieval
  problem than the actual product surface (`POST /ask` has no
  `meeting_id` requirement), and would have hidden the real cross-meeting
  ambiguity this phase's calibration run surfaced on `dec-3` (see
  Consequences).
- **Claude as the LLM-judge**, per ROADMAP.md's original Phase 5 wording.
  Superseded by ADR-0013, which made Gemini the sole active `LLMProvider`
  end-to-end, "for now, the eval LLM-judge" included, specifically to avoid
  requiring a second paid API key (`ANTHROPIC_API_KEY`) just to run the eval
  suite. This is the source of the self-preference-bias caveat above.
- **Gating on mean relevance and/or `answered_as_expected_rate` too.**
  Rejected for this dataset size -- see "CI gate" above. Revisit once the
  golden set (particularly the out-of-scope slice) is large enough that a
  single question's result doesn't swing the aggregate by double digits.
- **Replacing `df-2` with an easier direct-fact question** once it surfaced
  as the one retrieval miss during calibration. Rejected -- that would trade
  an honest, measured limitation for a threshold that always passes,
  defeating the point of building this harness at all.
- **Silently swallowing a golden-dataset quote that no longer matches any
  chunk.** Rejected in favor of `GoldenDatasetError` -- CLAUDE.md's "fail
  loudly and specifically" standard applies to the eval harness's own
  correctness as much as to production code; a mis-scored eval run is worse
  than a crashed one.

## Consequences

- **A 20-question golden set is a directional signal, not a statistically
  rigorous one.** Each category has 4-7 questions; a single question
  flipping category-level pass/fail changes that category's rate by
  15-25%. The aggregate gate is deliberately built on the two largest,
  least-noisy slices (17 in-scope questions for recall, all 20 for
  faithfulness) for exactly this reason, but the headline numbers in
  `eval/results/latest.json` should be read as "this system is behaving
  about this well on these representative categories of question," not as
  a statistically powered claim. A production-scale eval set would need:
  hundreds of questions per category (enough for real confidence intervals
  on each aggregate), sourced from actual logged user queries rather than
  hand-written ones (so the distribution matches real usage, including the
  paraphrased and multi-hop questions ADR-0007 already flags as this
  system's weak point), a held-out slice never used for threshold tuning
  (this phase's own threshold choice was informed by looking at the results
  it's now gating -- acceptable for a 20-question directional harness,
  a real methodological problem at production scale), and periodic
  re-labeling as the transcript corpus and product surface evolve.
- **Self-preference bias is accepted, not corrected for.** A future
  iteration with a second working `LLMProvider.generate_structured`
  implementation (the `AnthropicLLMProvider` gap ADR-0008 already names)
  could judge with a model from a different family than the one generating
  answers, removing this specific bias risk.
- **The eval suite costs a real external API budget on every CI run** --
  roughly 40 Gemini calls (2 per in-scope question) plus a from-scratch
  local embedding-model download per job, gated behind a
  `GEMINI_API_KEY` repository secret that must be provisioned for the
  `eval` CI job to run at all (see `.github/workflows/ci.yml`). This is a
  deliberate trade-off named directly in the assignment brief ("a real
  quality gate, not a report nobody reads") over a cheaper mocked-provider
  gate that would catch far less.
- **`df-2`'s retrieval gap is real and currently unfixed.** It's evidence
  (not yet acted on) that speaker-turn chunking can separate a short,
  context-dependent answer from the question that gives it meaning. A
  cross-encoder re-ranker over a wider candidate pool (ADR-0007's
  already-named future direction) or a chunking strategy that includes a
  short window of surrounding turns for very short chunks are both
  plausible fixes; neither was in scope for this phase, whose job was to
  measure and report the gap, not close it.

## Links

- ADR-0006 (chunking strategy) -- the speaker-turn merge behavior that
  motivated quote-anchored ground truth over hardcoded chunk indices, and
  the root cause of the `df-2` retrieval gap
- ADR-0007 (retrieval and citation strategy) -- names Phase 5 as the
  intended mechanism for tuning `top_k`/fusion weights; the cross-encoder
  re-ranker idea relevant to closing the `df-2` gap
- ADR-0008 (structured extraction and guardrails) -- names Phase 5 as the
  intended mechanism for tuning both confidence thresholds; the
  `generate_structured` gap on `AnthropicLLMProvider` relevant to the
  self-preference-bias limitation
- ADR-0013 (switch default LLM to Gemini) -- why Gemini judges Gemini, and
  the accepted self-preference-bias trade-off
- `ROADMAP.md` Phase 5 (evaluation harness wired into CI)
- `eval/golden_dataset/golden_questions.json`, `eval/golden.py`,
  `eval/metrics.py`, `eval/judge.py`, `eval/run_eval.py`
- `app/repositories/meeting_repository.py`
  (`get_by_source_filename`, added this phase for idempotent local eval runs)
- `.github/workflows/ci.yml` (`eval` job)
