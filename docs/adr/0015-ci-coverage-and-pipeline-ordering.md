# ADR-0015: Coverage tooling, the greenlet coverage blind spot, and fail-fast CI ordering

Status: Accepted
Date: 2026-07-13

## Context

Two related gaps surfaced while auditing test coverage and CI structure
against CLAUDE.md Section 2's "full meaningful coverage of business logic"
standard and Section 8's per-phase definition of done:

1. Neither app had coverage tooling wired up at all, so "no untested branch
   in chunking, retrieval, extraction, or guardrail logic" had never
   actually been measured, only assumed from reading the test suite.
2. `.github/workflows/ci.yml`'s `api` and `web` jobs ran lint, type-check,
   and a single combined test step in parallel with each other, and the
   `eval`/`mcp`/`docker-build` jobs were gated only on the `api` job. A
   broken web test, or a broken unit test hiding behind a slower
   integration test in the same `pytest -q` invocation, wasted CI time and
   didn't fail as early as it could.

Turning on coverage produced one finding that shaped everything else:
`apps/api`'s routers looked 60-75% covered despite integration tests that
clearly exercised their full happy path (e.g. `app/routers/ask.py`'s `_ask`
showed lines 66-104 as never executed, even though
`tests/integration/test_ask.py` asserts a 200 response with citations from
exactly that code path). The cause is `coverage.py`'s default tracer not
following the `greenlet` context switches SQLAlchemy's async engine uses
internally to bridge async/await onto the ORM's synchronous execution
machinery -- code that runs after such a switch is invisible to
`sys.settrace`-based coverage unless it's told to track greenlets
explicitly. Every router and repository that touched the database was
under-reported for this reason, not because of missing tests.

## Decision

**Coverage tooling:** added `pytest-cov` to `apps/api`'s dev dependencies
and `@vitest/coverage-v8` to `apps/web`'s, with branch coverage enabled in
both (`--cov-branch` / `vitest.config.ts`'s `coverage.provider: "v8"`).
`apps/api/pyproject.toml` sets:

```toml
[tool.coverage.run]
concurrency = ["greenlet", "thread"]
branch = true
source = ["app"]
```

`concurrency = ["greenlet", "thread"]` is the fix for the blind spot above --
without it, every DB-touching code path anywhere in `app/` under-reports
regardless of how thoroughly it's actually tested.

With that fix in place, real remaining gaps were small and specific:
`VoyageEmbeddingProvider.embed()` (no test at all, mocked or otherwise),
`get_configured_model_name`'s unknown-provider branch, the local BGE
provider's model-caching branch, `dependencies.py`'s production DI wiring
(always overridden by `app.dependency_overrides` in tests, never exercised
for real), `MeetingRepository.add_extractions` actually setting
`meeting_id` (every existing test happened to extract an empty payload), a
non-UTF-8 upload's 422 path, and one missing 404 test. On the frontend,
`app/lib/api/client.ts` -- the entire fetch/error-handling/query-building
layer -- was 25% covered because every component test mocks it; its own
behavior had never been exercised directly. All of these were filled with
real tests, not coverage-chasing busywork; see the commits touching
`apps/api/tests/` and `apps/web/app/lib/api/client.test.ts`.

Two things were deliberately left uncovered rather than gamed: the
`raise NotImplementedError` bodies of `EmbeddingProvider`/`LLMProvider`'s
`@abstractmethod` stubs (unreachable -- Python's `ABC` prevents
instantiating the base class, so the statement can never execute), and one
branch in `chunking.py`'s `_split_oversized_turn` (the `if
current_sentences:` false case at the end of the loop, which would require
`_split_into_sentences` to return an empty list -- a guarantee it never
breaks, since it always falls back to `[text]`). Testing either would mean
writing a test whose only purpose is satisfying a coverage percentage, not
guarding against a real failure mode.

Also found and flagged, not fixed: `app/lib/api/useAsyncState.ts` is dead
code. ADR-0014 documents it as the shared `{data, loading, error}` hook
every view should use, but no component actually imports it -- every
list/detail view hand-rolls the identical triple instead. Left alone here
(fixing it means touching ~6 component files, out of scope for a coverage
pass) but recorded so it doesn't silently stay stale.

**CI ordering:** `apps/api`'s `pytest -q` step split into
`pytest -q tests/unit` then `pytest -q tests/integration` as two separate
steps, so a broken unit test fails before the slower Postgres-backed
integration suite runs. The `mcp` job's `needs` grew from `[api]` to
`[api, web]` (later, `[api, web, mcp]` before `docker-build`) so the whole
lint/type-check/test lane -- both stacks, not just the backend -- gates
anything downstream. `docker-build` now tags images with both a moving
`:ci` tag and the immutable commit SHA
(`docker build -t meridian-api:ci -t meridian-api:${{ github.sha }} ...`),
so a specific built image can be traced back to the commit it came from.

(The `eval` job's place in this ordering was revised again almost
immediately after -- see ADR-0016, which supersedes this ADR's original
"eval-suite gate runs on every push, gating `docker-build`" arrangement.)

## Alternatives considered

- **Chase the coverage numbers directly (write tests until routers hit
  90%+) without investigating why they were low.** Would have produced
  dozens of redundant tests re-asserting behavior the integration suite
  already covered, without fixing the actual measurement defect -- the next
  new router would have shown the same false gap.
- **Disable branch coverage to avoid the partial-branch noise in
  `chunking.py` and `local_bge_provider.py`.** Rejected: branch coverage is
  what surfaced the one genuine gap in `local_bge_provider.py`'s
  model-caching path; turning it off to silence one dead branch would have
  hidden a real one too.
- **Merge `api` and `web` into one sequential CI job for stricter
  "in order" semantics.** Rejected: they're independent stacks (CLAUDE.md
  Section 5's monorepo layout) with no reason to serialize their lint/test
  runs; gating everything downstream on *both* finishing achieves the same
  fail-fast guarantee without losing that parallelism.

## Consequences

- Coverage reports are now a real, trustworthy signal for both apps, not an
  unmeasured assumption -- and the greenlet fix means that stays true as
  new DB-touching code is added, not just for what exists today.
- Anyone adding a new SQLAlchemy-async code path in `apps/api` should know
  about the `concurrency` setting before concluding a low coverage number
  means untested code; it might mean the opposite.
- `useAsyncState.ts` remains a known, tracked piece of debt: either wire it
  into the views ADR-0014 says should use it, or delete it, next time
  frontend state-management code in this area is touched.
- CI now fails faster and cheaper on the common case (a broken unit test),
  at the cost of a slightly longer YAML file to read.

## Links

- ADR-0003 (custom orchestration vs. framework; the ports-and-adapters
  interfaces whose provider implementations this pass tested directly)
- ADR-0004 (embedding provider choice; `VoyageEmbeddingProvider` and
  `LocalBGEEmbeddingProvider` gaps closed here)
- ADR-0013 (Gemini as default LLM; `get_configured_model_name` gap closed
  here)
- ADR-0014 (frontend architecture; `useAsyncState.ts` origin and the drift
  flagged above)
- ADR-0016 (moves the eval-suite gate out of this ordering entirely)
- `apps/api/pyproject.toml` (`[tool.coverage.run]`)
- `apps/web/vitest.config.ts` (`test.coverage`)
- `.github/workflows/ci.yml`
