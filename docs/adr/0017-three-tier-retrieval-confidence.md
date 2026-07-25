# ADR-0017: Three-tier retrieval confidence (low-confidence middle ground)

Status: Accepted
Date: 2026-07-24

## Context

ADR-0008 established `passes_retrieval_confidence`: a binary guardrail on
`POST /ask` and `POST /meetings/{id}/ask` that either attempts an answer or
declines outright with a fixed "not well-supported" response, based on
retrieved chunks' raw vector/text scores against `retrieval_confidence_threshold`.

Binary is too coarse for a real question that sits just below the
threshold -- there's a real difference between "nothing retrieved is
grounded at all" and "the best match is somewhat weak, but plausibly still
useful." The system had no way to express the second case; both collapsed
into the same outright decline.

## Decision

`passes_retrieval_confidence(retrieved, threshold) -> bool` is replaced by
`classify_retrieval_confidence(retrieved, *, threshold, low_confidence_floor) -> ConfidenceTier`,
a three-way classification:

- **CONFIDENT** -- a real full-text match (unchanged from before: Postgres's
  `@@` operator only ever matches on genuine lexical overlap, so its
  presence alone is trusted regardless of vector score), or the best raw
  vector score is at or above `threshold`.
- **LOW_CONFIDENCE** -- no full-text match, and the best raw vector score is
  below `threshold` but at or above a new, lower `low_confidence_floor`.
  The system still attempts an answer, but flags the response.
- **DECLINE** -- nothing retrieved at all, or the best raw vector score is
  below `low_confidence_floor`. Same outright-decline behavior as before,
  unchanged at the bottom end.

`retrieval_low_confidence_floor` (default `0.15`, alongside
`retrieval_confidence_threshold`'s `0.3`) is a new setting in `config.py` --
a starting heuristic in the same spirit as the original threshold, pending
Phase 5's eval harness.

`AskResponse` gained `low_confidence: bool = False`. `ask.py`'s `_ask()`
still returns the fixed "not well-supported" answer immediately on
`DECLINE`, without calling `generate_answer` at all (unchanged). On
`LOW_CONFIDENCE`, it proceeds through the existing `generate_answer` /
citation-enforcement path exactly as `CONFIDENT` does, and only sets
`low_confidence=True` on the response before returning -- the guardrail
adds a label, not a second code path through generation.

`ConfidenceTier` is a `StrEnum`, not two independent booleans (e.g.
`declined: bool` + `low_confidence: bool`), because the three outcomes are
mutually exclusive states of one underlying judgment, not two orthogonal
flags -- there's no meaningful combination where, say, both `declined` and
`low_confidence` are true at once.

## Alternatives considered

- **A second boolean parameter/return value** (`passes: bool, low_confidence: bool`)
  instead of an enum. Rejected -- two booleans can represent an invalid
  combination (`passes=False, low_confidence=True`) that the domain doesn't
  actually have; an enum makes the illegal state unrepresentable.
- **Expressing the middle tier as a numeric confidence score on the response**
  (e.g. `confidence: float` mirrored from the raw retrieval score) instead of
  a boolean flag. Rejected for this pass -- a raw score on the response
  invites the frontend (or a caller) to pick its own arbitrary display
  threshold, re-deriving a decision the backend guardrail should own
  outright. A boolean flag keeps "is this trustworthy enough to label" as a
  single backend decision, consistent with how `supported` already works.
- **Keeping `passes_retrieval_confidence` alongside the new function** for
  backward compatibility. Rejected -- `classify_retrieval_confidence` is a
  strict superset of the old function's behavior (`CONFIDENT`/`DECLINE` at
  the same boundaries), so keeping both would be the exact copy-pasted-logic
  situation CLAUDE.md's DRY rule rules out. The old function's unit tests
  were migrated to test the new one at the same boundary values, plus new
  tests for the added `LOW_CONFIDENCE` band.

## Consequences

- `retrieval_low_confidence_floor` (`0.15`) is a starting heuristic chosen by
  reasoning, not measurement -- the same posture ADR-0008 already took
  toward `retrieval_confidence_threshold` and ADR-0007 took toward `top_k`
  and the fusion weights. Phase 5's eval harness is the intended mechanism
  for tuning it with real evidence.
- The frontend does not yet render `low_confidence` visually (no caveat
  badge on the answer panel yet) -- the backend now emits the signal, but
  surfacing it in `ChatView.tsx` is a follow-up, not part of this change.
- `eval/run_eval.py` also called `passes_retrieval_confidence` directly (to
  mirror `_ask()`'s guardrail step when scoring the golden dataset) and was
  updated alongside `ask.py` to call `classify_retrieval_confidence` and
  treat only `ConfidenceTier.DECLINE` as the decline path -- `LOW_CONFIDENCE`
  is scored the same way `CONFIDENT` is, matching production behavior.

## Links

- ADR-0008 (structured extraction and guardrails -- the original binary
  guardrail this supersedes)
- ADR-0007 (retrieval and citation strategy -- raw vs. fused score reasoning
  this ADR's CONFIDENT/DECLINE boundary reuses unchanged)
- `app/services/guardrails/output_guardrail.py`, `app/routers/ask.py`,
  `app/config.py`, `app/models/schemas.py`
- `tests/unit/test_output_guardrail.py`
- `ROADMAP.md` Phase 5 (evaluation harness -- intended mechanism for tuning
  `retrieval_low_confidence_floor`)
