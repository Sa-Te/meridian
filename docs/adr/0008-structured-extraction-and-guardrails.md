# ADR-0008: Structured extraction and guardrails

Status: Accepted
Date: 2026-07-11

## Context

Phase 4 is the "Guardrails, Quality Controls" assignment checkpoint, and the
piece that separates Meridian from a plain document-QA bot: decisions and
action items need to be extracted automatically at ingestion time, and the
pipeline needs guardrails that are a distinct, testable module rather than
inline checks scattered through services.

ADR-0007 (Phase 3) deliberately left two things open for this phase:

- Citation enforcement was built as plain-JSON-prompt + Pydantic validation,
  "keeping generation fully vendor-agnostic... reconsidered if Phase 4's
  extraction work needs it, where the more complex Decision/ActionItem shape
  is a better argument for it."
- A confidence-threshold cutoff on retrieval, "deliberately deferred to
  Phase 4, which names this exact idea... as its own guardrail."

Both are resolved below, along with the input guardrail (prompt-injection
scanning) and the new read endpoints.

## Decision

### Structured extraction via native structured output, scoped to Gemini

`LLMProvider` gained a second abstract method alongside `generate`:

```python
async def generate_structured(
    self, prompt: str, response_model: type[SchemaT], *, system=None, max_tokens=1024, temperature=0.0
) -> SchemaT
```

It takes a Pydantic model class and returns a validated instance directly --
no manual JSON parsing at the call site, unlike `generate`'s plain-text
contract. `GeminiLLMProvider.generate_structured` uses Gemini's native
structured-output mode (`response_mime_type="application/json"` plus
`response_schema=response_model`, which `google-genai` 2.x accepts as a
Pydantic class directly), then still re-validates the returned JSON on our
own side via `response_model.model_validate_json` rather than trusting the
vendor's schema conformance as the only check -- the same "the vendor's
guarantee isn't the only check" posture as Phase 3's citation guardrail.

`AnthropicLLMProvider.generate_structured` raises `NotImplementedError`
rather than a blind implementation. The Anthropic equivalent is forced tool
use (a tool whose `input_schema` mirrors `response_model`, with
`tool_choice` forcing that tool) -- a genuinely different code path from
Gemini's `response_schema` mode, and this project's own standard (CLAUDE.md
Section 2: every module gets real tests in the same change that introduces
it) ruled out writing it without a working `ANTHROPIC_API_KEY` to verify
against. `LLM_PROVIDER=gemini` remains the only path extraction supports;
this is a deliberate, documented gap, not an oversight -- see Consequences
and the README's "what I'd do differently" section.

`app/services/extraction.py` builds one prompt per meeting from its already-
stored chunks (each tagged `[chunk_id: ...] [Ns] Speaker: text`, the same
excerpt format as Phase 3's answer generation), asks for a payload of
`decisions: list[Decision]` and `action_items: list[ActionItem]`, and
guardrail-filters the result (below) before handing ORM objects to
`MeetingRepository.add_extractions`. This runs in `POST /meetings/ingest`
immediately after chunking/embedding/storage, so every candidate
`source_chunk_id` extraction can cite is already a real, persisted chunk id.

### Guardrails as their own package: `app/services/guardrails/`

- **`input_guardrail.py`** -- `scan_for_prompt_injection(text)` checks text
  against a fixed list of regex patterns for common prompt-injection
  phrasings (instructions addressed to an AI, attempts to override prior
  instructions, requests to reveal a system prompt, and similar).
  `scan_chunks_for_prompt_injection(chunks)` runs this per-chunk (after
  chunking, so findings can be tagged with a `chunk_index`) and is called
  from the ingest endpoint. This is **detection, not sanitization**: a match
  is surfaced as `flagged_for_prompt_injection` / `prompt_injection_findings`
  on the `IngestResponse`, and the transcript is still chunked, embedded,
  and passed to extraction/generation as usual. A machine can't reliably
  tell an actual attack apart from a meeting participant reading a prompt
  out loud as part of a legitimate discussion; flagging leaves that call to
  a human reviewer instead of guessing.
- **`output_guardrail.py`** -- two checks:
  - `citation_ids_are_valid(cited_ids, valid_ids)` generalizes Phase 3's
    inline citation check (`cited_ids` non-empty and a subset of
    `valid_ids`) into a shared function. `answer_generation.py` uses it for
    a list of citations per answer; `extraction.py` uses it for a single
    `source_chunk_id` per extracted item, via
    `citation_ids_are_valid([source_chunk_id], valid_ids)`.
  - `passes_retrieval_confidence(retrieved, threshold)` -- the confidence
    threshold ADR-0007 deferred. See the next section for why this checks
    each chunk's **raw** vector similarity rather than the fused score
    ADR-0007's wording literally suggested.

`app/services/llm_json.py` also picked up `strip_code_fence`, moved out of
`answer_generation.py` unchanged -- a small DRY cleanup so extraction could
reuse it too, though in the end extraction doesn't need it (native
structured output has no code-fence-wrapping failure mode; only
`answer_generation.py`'s plain-JSON path does).

### Why the confidence threshold uses raw vector score, not the fused score

ADR-0007 named the deferred idea as "a confidence-threshold cutoff on the
fused score." Implementing it that way turns out not to work: `fuse_scores`
min-max normalizes each signal *within the current candidate set* before
weighting, which means the single best candidate on a given side always
normalizes to (or very near) `1.0` -- regardless of whether it is actually
relevant. Vector search in particular always returns its nearest neighbors,
never "no match"; for a totally out-of-scope question, the top vector
candidate would still normalize to `1.0` and produce a deceptively high
fused score.

`passes_retrieval_confidence` instead checks each retrieved chunk's *raw*,
pre-normalization `vector_score`/`text_score` (both now carried on
`RetrievedChunk`, alongside the existing `fused_score`, purely for this
guardrail's benefit). A real full-text match (`text_score is not None`)
passes on its own, with no threshold needed -- Postgres's `@@` operator only
ever returns a row when a genuine lexical match exists, so its mere presence
is already meaningful, unlike a naturally-always-populated vector score.
Absent that, the guardrail requires some chunk's raw cosine similarity to
clear `retrieval_confidence_threshold` (default `0.3`, a starting heuristic
like ADR-0007's `top_k`/weights, pending Phase 5's eval harness). This is
wired into `ask.py`'s `_ask()` before `generate_answer` is even called: a
failing check returns the fixed "not well-supported" answer directly,
without spending an LLM call.

A **self-reported LLM confidence field** (asking the model to grade its own
answer 0-1) was considered and rejected for this guardrail -- asking a model
to self-assess confidence is a known-unreliable pattern, and the retrieval
score is an objective, independently-computed signal that doesn't depend on
the same model being well-calibrated about itself.

### Per-item guardrail filtering, not all-or-nothing

Phase 3's citation guardrail is all-or-nothing: one invalid citation fails
the *entire* answer, which is correct when there's one answer. Extraction
produces a batch of several decisions/action items per meeting, so
`_filter_guardrailed` in `extraction.py` drops only the individual item that
fails (a `source_chunk_id` outside the meeting's real chunks, or a
self-reported `confidence` below `extraction_confidence_threshold`, default
`0.5`), keeping every other item in the same response. A malformed/
non-conforming structured response as a whole (parse failure) still gets
the Phase-3-style one retry with a stricter instruction, then falls back to
zero extractions for that meeting -- extraction is a best-effort
augmentation; the meeting and its chunks are already safely stored by that
point regardless of whether extraction succeeds.

### New read endpoints

`GET /meetings/{id}/decisions` and `GET /meetings/{id}/action-items` extend
`MeetingRepository.get_by_id`'s eager-loading to include those two
relationships. The global `GET /action-items?status=&owner=` needed a
cross-aggregate read the same way Phase 3's retrieval did, so it gets its
own `ActionItemRepository` -- the same "read query spanning the aggregate
boundary doesn't belong in `MeetingRepository`" reasoning ADR-0007 already
established for `ChunkRepository`. Filtering is exact-match on `status`
(the native enum) and `owner` (string equality); no pagination, matching the
ROADMAP's "basic filtering" scope for this phase.

`MeetingRepository.add_extractions` sets `meeting_id` directly on each
extracted `Decision`/`ActionItem` and adds them individually via
`session.add_all`, rather than assigning `meeting.decisions = [...]`.
Assigning a relationship collection makes SQLAlchemy's ORM lazy-load the
*current* collection first (to diff against for the unit of work), which
isn't safe to do implicitly from an async context without `AsyncAttrs` --
it raised `MissingGreenlet` in testing. Setting the foreign key directly and
adding children individually avoids touching the collection at all.

### PII: no redaction implemented

The transcripts are synthetic and health-*adjacent* (a health-tech
consulting engagement discussing product decisions, alert thresholds,
pilot programs), not real patient health information -- there's no genuine
PHI in this dataset to protect. Building a redaction pass here would be
protecting nothing while adding real complexity (a PII/PHI detector,
redaction-vs-hashing-vs-tokenization decisions, and a policy for how
redaction interacts with citation-to-source-chunk, which needs the original
text to remain meaningful). This is a real, explicit gap for anything
handling actual patient data: a production version of this system, ingesting
real clinical meeting transcripts, would need a dedicated PII/PHI detection
and redaction stage before any external LLM call, not just at rest.
Documented here rather than silently absent; noted again in the README's
"what I'd do differently" section per CLAUDE.md Section 9's framing.

## Alternatives considered

- **Anthropic tool-use for `generate_structured`, implemented now.**
  Rejected for this submission -- no working `ANTHROPIC_API_KEY` was
  available to build and verify it against, and shipping an untested vendor
  integration violates this project's own testing standard more than
  shipping a documented `NotImplementedError` does. `LLM_PROVIDER=gemini`
  is already the required default end-to-end path (ADR-0013), so this
  doesn't block the system from working; it blocks only the
  `LLM_PROVIDER=anthropic` config from covering extraction, which is
  already true today for other reasons.
- **Whole-payload retry-on-any-invalid-item for extraction**, mirroring
  Phase 3 exactly. Rejected: discarding four correct extractions because a
  fifth cited a hallucinated chunk id throws away real, verifiable work for
  no benefit -- per-item filtering achieves the same "never trust an
  unverifiable claim" guarantee without that cost.
- **Confidence threshold on the fused/normalized retrieval score**, as
  ADR-0007's wording literally suggested. Rejected once implemented and
  reasoned through -- see "Why the confidence threshold uses raw vector
  score" above; min-max normalization guarantees a locally-high score
  regardless of true relevance, which defeats the point of a threshold.
- **LLM self-reported confidence** for the ask flow's guardrail. Rejected in
  favor of the retrieval score -- a model grading its own certainty is a
  well-known unreliable pattern; an independently-computed retrieval
  signal isn't subject to the same self-assessment failure mode.
- **A fuller prompt-injection classifier** (a small fine-tuned model, or an
  LLM-as-classifier call) instead of a fixed regex pattern list. Rejected
  for this submission on scope/time grounds: the regex list only catches
  known, common phrasings and a determined adversary can phrase around any
  fixed pattern -- a real, acknowledged limitation, not a claim of robust
  detection. Documented as a "with more time" item.
- **PII/PHI redaction.** Considered and explicitly not implemented -- see
  "PII: no redaction implemented" above.

## Consequences

- Extraction only works end-to-end with `LLM_PROVIDER=gemini`. This is
  consistent with ADR-0013 (Gemini is already the sole required default),
  but it does mean the `AnthropicLLMProvider` abstraction, while still
  proving the `LLMProvider` interface works for `generate`, is not a
  complete drop-in replacement until `generate_structured` is implemented
  for it -- a concrete, scoped follow-up rather than a vague gap.
- The prompt-injection scan is a heuristic, not a guarantee; it will miss a
  sufficiently paraphrased or obfuscated injection attempt. It is flagging,
  not filtering, by design, so even a missed detection doesn't change
  system behavior beyond the flag itself being absent.
- `retrieval_confidence_threshold` (`0.3`) and `extraction_confidence_threshold`
  (`0.5`) are both starting heuristics chosen by reasoning, not measurement --
  Phase 5's eval harness is the intended mechanism for tuning both with real
  evidence, the same posture ADR-0007 took toward `top_k` and the fusion
  weights.
- Real patient data was explicitly never in scope for this dataset; anyone
  extending this system to real clinical transcripts must treat PII/PHI
  redaction as a blocking prerequisite, not an optional enhancement.

## Links

- ADR-0002 (core tech stack -- ports and adapters for `LLMProvider`)
- ADR-0003 (custom orchestration vs. framework)
- ADR-0005 (domain schema -- `Decision`/`ActionItem`, required `source_chunk_id`)
- ADR-0007 (retrieval and citation strategy -- both deferred items this ADR resolves)
- ADR-0013 (switch default LLM to Gemini)
- `app/providers/llm/base.py`, `app/providers/llm/gemini_provider.py`,
  `app/providers/llm/anthropic_provider.py`
- `app/services/extraction.py`, `app/services/guardrails/`,
  `app/services/answer_generation.py`, `app/services/retrieval.py`
- `app/repositories/meeting_repository.py`, `app/repositories/action_item_repository.py`
- `app/routers/meetings.py`, `app/routers/action_items.py`, `app/routers/ask.py`
- `ROADMAP.md` Phase 4 (structured extraction and guardrails) and Phase 5
  (evaluation harness -- the intended mechanism for tuning the confidence
  thresholds introduced here)
