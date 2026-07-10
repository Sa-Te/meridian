# ADR-0013: Switch the default LLM provider from Anthropic to Gemini

Status: Accepted
Date: 2026-07-10

## Context

ADR-0002 set Anthropic Claude as the default LLM for generation, structured
extraction, and the eval LLM-judge, with the explicit goal of keeping the
whole system runnable end to end on a single external API key. In practice,
the Anthropic trial credit used for this project's development required
adding a payment method sooner than expected to keep making API calls. That
is not viable for the iterative, call-heavy way this project is being built
(repeated ingestion runs, retrieval experiments, eval-suite runs during
active development) without turning a take-home assignment into a recurring
paid expense.

Google's Gemini API offers a genuinely free tier (an API key from Google AI
Studio, no billing account attached) with a model in the same "cheap, fast,
good enough for RAG generation and judging" class as Claude's smaller
models. Switching the *default* provider preserves ADR-0002's original goal
(single external key, zero-cost to run for a reviewer) better than the
original choice now does.

## Decision

`LLM_PROVIDER` defaults to `gemini`. `GeminiLLMProvider` is the active
default implementation of the `LLMProvider` interface defined in ADR-0002 /
ADR-0003, used for generation and, for now, the eval harness's LLM-judge.
Default model: `gemini-3.1-flash-lite`, confirmed live via the Gemini
`ListModels` API as the current stable (non-preview) Flash-Lite release at
the time of this decision -- pinned explicitly rather than tracked via the
`gemini-flash-lite-latest` alias, so a Google-side model swap can't silently
change behavior underneath this project.

`AnthropicLLMProvider` remains in the codebase as a second concrete
`LLMProvider` implementation, selectable via `LLM_PROVIDER=anthropic`. It is
not required: no code path reads `ANTHROPIC_API_KEY` unless that provider is
explicitly selected, and `Settings.anthropic_api_key` defaults to `None`.
The app runs end to end with only `GEMINI_API_KEY` populated.

This supersedes only the LLM-provider-choice paragraph of ADR-0002 (see the
amendment note added there). ADR-0002's other stack choices, and ADR-0003's
reasoning for keeping generation behind a swappable interface at all, both
stand unchanged -- this decision is exactly the kind of vendor swap that
abstraction was built to absorb cheaply, and it did: this change touched
only the provider layer and config, not retrieval, extraction, or any
business logic (none of which exist yet as of this ADR, but the interface
was written to that constraint regardless).

## Alternatives considered

- **Add a payment method to the Anthropic account and keep Claude as
  default.** Rejected for this submission: real recurring cost for a take-
  home project with an indefinite development timeline, when a free
  alternative in the same capability class exists.
- **OpenAI as the default instead of Gemini.** Also requires a paid API key
  with no meaningful free tier for a project of this call volume. Rejected
  for the same cost reasoning; still available behind the interface if a
  budget opens up later.
- **Keep Anthropic as default, only call it sparingly / mock it during
  development.** Rejected: mocking the actual LLM during iterative RAG
  development defeats the purpose of building a real system to learn from,
  and the assignment is explicitly evaluated end to end, not on mocked
  output.

## Consequences

- **Free-tier data usage.** Per Google's Gemini API Additional Terms of
  Service, content submitted on the free (unpaid) tier -- prompts and
  generated responses -- may be used by Google "to provide, improve, and
  develop Google products and services and machine learning technologies."
  The paid tier explicitly excludes this. Running this project's demo data
  (synthetic health-tech transcripts, not real patient data) through the
  free tier is an acceptable trade-off here specifically because the
  dataset is synthetic; this would not be an acceptable default for a real
  deployment handling real client transcripts, and the README's
  productionization section should say so.
  (https://ai.google.dev/gemini-api/terms)
- **Free-tier rate limits are not a stable contract.** Google's own rate-
  limits documentation states limits vary by model and usage tier and are
  "not guaranteed" -- actual capacity may vary and change without the kind
  of advance notice a paid SLA would carry. Ingestion or eval runs that
  batch many calls in a short window may need retry/backoff handling as a
  result; this is a real operational gap for now, not yet built, and
  worth flagging if throttling is observed during later phases.
  (https://ai.google.dev/gemini-api/docs/rate-limits)
- **Self-preference bias in the eval harness (the significant one).** The
  eval harness's LLM-judge is specified in ROADMAP Phase 5 to score the
  generator's own output for faithfulness and relevance. With this ADR,
  generation and judging both run on Gemini. Using the same model (even the
  same vendor) as both generator and judge is a known methodological
  weakness in LLM-as-judge setups: models are measurably biased toward
  favorably scoring outputs that match their own generation style and
  tendencies, independent of actual quality. This is **not solved** in this
  submission -- it is a real limitation being knowingly accepted, not an
  oversight. The correct fix is a cross-vendor judge (e.g. Claude judging
  Gemini's output, or vice versa), which requires a second provider's
  budget. This is called out explicitly as a "what I'd do differently with
  more time" item for the README (Section 8), not a throwaway caveat --
  when Phase 5 (evaluation harness) is built, its ADR should restate this
  limitation and link back here rather than silently reusing Gemini as
  judge without comment.
- **Interface abstraction cost paid off immediately.** This is the first
  real test of ADR-0003's provider-interface reasoning: swapping the active
  default LLM vendor required adding one new adapter file and one config
  default, with zero changes anywhere a provider is consumed.

## Links

- ADR-0002 (core tech stack -- amended)
- ADR-0003 (custom orchestration vs. framework; provider abstraction)
- `ROADMAP.md` Phase 5 (evaluation harness -- restate the judge limitation
  when this lands)
- `apps/api/app/providers/llm/` (interface and both implementations)
