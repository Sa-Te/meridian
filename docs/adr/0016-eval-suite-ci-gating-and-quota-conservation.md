# ADR-0016: Move the eval-suite gate off the per-push CI pipeline

Status: Accepted
Date: 2026-07-13

## Context

ADR-0013 flagged this risk in advance: "Ingestion or eval runs that batch
many calls in a short window may need retry/backoff handling... a real
operational gap for now, not yet built, and worth flagging if throttling
is observed." It was observed. `.github/workflows/ci.yml`'s `eval` job (see
ADR-0015) ran on every `push` and `pull_request` -- meaning every commit on
every feature branch, not just merges to `main` -- and each run scores all
20 golden questions, spending two real Gemini calls per in-scope question
(one `generate_answer`, one `judge_answer`) via the free-tier
`GEMINI_API_KEY` shared across the whole project. That key also caps
requests-per-day, not just requests-per-minute (the harness's existing
`_LLMRateLimiter` only paces the latter). Several pushes in a short working
session were enough to exhaust the daily cap and start failing CI runs for
reasons that had nothing to do with the code under review.

Auditing where real API calls actually happen in CI (per this ADR's
trigger) found the `eval` job's per-push frequency was the entire problem,
not test hygiene:

- Every unit/integration test in `apps/api` already uses
  `tests/fakes.py`'s `FakeLLMProvider`, exactly as ADR-0003's interface
  abstraction was built to allow. The one exception,
  `tests/integration/test_extraction.py`, is deliberately real (its own
  docstring: "the one integration test in this suite that spends a real
  LLM call, since `GeminiLLMProvider.generate_structured` is the part of
  this phase that can't be meaningfully verified against a fake") and is
  already `pytest.mark.skipif`-gated on a real `GEMINI_API_KEY` being
  configured. The `api` CI job never sets that secret, so this test is
  skipped in CI today and always has been -- zero real calls from it.
- `apps/mcp_server/tests/test_smoke.py`'s `ask_meetings` smoke test runs
  against a live `uvicorn` process in the `mcp` job, which *does* get a
  real `GEMINI_API_KEY`. It still spends zero real calls: the job's
  database is freshly migrated with no ingested meetings, so
  `passes_retrieval_confidence` (`app/services/guardrails/
  output_guardrail.py`) declines on the empty retrieval set before
  `_ask` ever reaches `generate_answer`. Noted as a fragile assumption
  (see Consequences), not a currently-real leak.
- `eval/tests/` (unit tests for the golden-dataset loader, the judge
  prompt builder, and the retry wrapper) were never wired into any CI job
  at all -- a pre-existing gap, unrelated to quota, fixed alongside this
  change since it was the natural moment to place it correctly (see
  Decision).

So: no test was quietly calling the real model when it should have used a
fake. The fix is entirely about *when* the one job that legitimately needs
real calls gets to run.

## Decision

1. **The eval-suite gate moved to its own workflow**,
   `.github/workflows/eval.yml`, triggered on `push: branches: [main]` and
   `workflow_dispatch`. It no longer runs on feature-branch pushes or pull
   requests, and `docker-build` in `ci.yml` no longer depends on it --
   `docker-build` now gates on `[api, web, mcp]` only. Quality regressions
   are still caught (on every merge to `main`, and on demand via manual
   dispatch for anyone who wants a read before merging something
   eval-sensitive), just not on every single commit of in-progress work.

2. **`eval/tests/` now runs inside the `api` CI job** (`python -m pytest -q
   eval/tests`, from the repo root so both `app` and `eval` resolve),
   immediately after `apps/api`'s own unit and integration tests. These
   tests use fakes/stubs exclusively (see `eval/tests/test_judge.py`'s
   `_StubLLMProvider`, `eval/tests/test_caching_llm_provider.py`'s
   `_CountingLLMProvider`) and need no real API key, so they belong in the
   fast, always-on lane, not the slow one.

3. **A short-lived in-process cache**, `eval/caching_llm_provider.py`'s
   `CachingLLMProvider`, wraps whichever real `LLMProvider` the harness is
   configured with (`eval/run_eval.py`'s `run()`:
   `llm_provider = CachingLLMProvider(get_llm_provider(settings))`).
   Keyed on the exact call arguments (messages/prompt, system, schema,
   max_tokens, temperature) and scoped to one `run()` invocation -- a fresh
   instance every run, nothing persisted to disk. Only successful
   responses are cached, so a call that fails is still retried for real by
   `_with_retry` rather than replaying a cached exception. Today's 20
   golden questions are all textually distinct, so this produces zero
   cache hits against the current dataset; it exists to make identical
   repeated calls free the moment a future golden-dataset entry duplicates
   a question, or the harness is invoked more than once in one process, at
   no cost to correctness now.

## Alternatives considered

- **Keep `eval` in `ci.yml` but only trigger it on `push` to `main`,
  leaving `pull_request` out, via a job-level `if:` condition.** Rejected
  in favor of a fully separate workflow file: the eval job's own trigger
  block (`on: push: branches: [main]`, `workflow_dispatch`) is more
  legible than a conditional buried in a job that otherwise looks
  identical to every other push-triggered job in `ci.yml`, and
  `workflow_dispatch` on a dedicated workflow gives a clean "run eval now"
  button in the Actions UI without one more input to wire through `ci.yml`
  itself.
- **Add a persistent, disk-backed response cache (e.g. keyed by golden
  question id, committed to the repo) instead of an in-process one.**
  Rejected: a fixture cache that silently goes stale the moment a prompt,
  model, or transcript changes is worse than no cache -- it would report a
  gate as passing against golden responses that no longer reflect what the
  real model actually returns today. The in-process cache only ever
  reflects calls made *in this run*, so it can't go stale between runs.
- **Increase `_MIN_LLM_CALL_INTERVAL_SECONDS` or add jitter instead of
  changing the trigger.** Would reduce RPM pressure but does nothing for
  the requests-per-day cap, which is what repeated per-push runs actually
  exhausted. Pacing and trigger frequency are solving different limits;
  both matter, but only the trigger change addresses the daily cap.
- **Mock Gemini in the eval harness entirely.** Rejected for the same
  reason ADR-0013 rejected it for day-to-day development: the eval
  harness's entire purpose is scoring the real model's real retrieval and
  generation quality; a mocked eval gate would pass unconditionally and
  catch nothing.

## Consequences

- **A normal PR / feature-branch push now spends zero real Gemini API
  calls in CI**, down from up to 40 (20 golden questions x 2 calls each) on
  every single push before this change. See the verification run in the
  commit introducing this ADR for the exact before/after count.
- Quality regressions are now visible on `main` (post-merge) rather than
  pre-merge on every branch push. This trades earlier-in-PR quality
  feedback for quota sustainability; `workflow_dispatch` is the escape
  hatch when a PR specifically touches retrieval/generation/guardrail
  logic and someone wants a read before merging.
- The `mcp` job's zero-real-calls property depends on its CI database
  staying empty. If a future change seeds that job's database with
  ingested meetings (e.g. to test citation content, not just response
  shape), `ask_meetings`' smoke test would start spending a real call on
  every push again -- worth another look at that point, not a risk today.
- The in-process cache adds a small amount of indirection
  (`CachingLLMProvider` wraps every real call) for no measurable benefit
  against the current golden dataset; its payoff is entirely about
  guarding future runs, not today's.

## Links

- ADR-0009 (evaluation methodology; the gate this workflow enforces)
- ADR-0013 (Gemini as default LLM; predicted this exact rate-limit risk)
- ADR-0015 (the per-push CI ordering this ADR partially supersedes --
  `eval` no longer gates `docker-build` in `ci.yml`)
- `.github/workflows/eval.yml`
- `.github/workflows/ci.yml` (`docker-build`'s `needs`, the `eval/tests`
  step in the `api` job)
- `eval/caching_llm_provider.py`
- `apps/api/tests/fakes.py` (`FakeLLMProvider`, already the standard for
  every non-real-model test)
- `apps/api/tests/integration/test_extraction.py` (the one intentionally
  real integration test, unchanged by this ADR)
