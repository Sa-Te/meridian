# ADR-0010: Observability approach

Status: Accepted
Date: 2026-07-11

## Context

Phase 6 is the "Observability" assignment checkpoint: every ask and
ingest+extraction call should produce a structured trace record (stages,
latencies, tokens, retrieval scores, model used) queryable via an API,
instrumented "without polluting business logic -- a decorator or context
manager, not inline timing calls scattered through services."

That last constraint is the real design problem. Phases 2-5 built four
service modules (`retrieval.py`, `answer_generation.py`, `extraction.py`,
`ingestion.py`) that are already unit-tested in isolation, with no
knowledge of HTTP, tracing, or persistence beyond their own repository
calls. The instrumentation approach had to add real, per-stage timing and
usage data without adding an import, a parameter, or a line of tracing
logic to any of those four files.

## Decision

### Instrumentation lives at two seams, never inside a service module

1. **Provider-port decorators** (`app/services/tracing.py`):
   `TracingEmbeddingProvider` and `TracingLLMProvider` both implement the
   existing `EmbeddingProvider`/`LLMProvider` interfaces (ADR-0002/0003's
   ports-and-adapters boundary) and wrap a real provider instance. Every
   `embed`/`generate`/`generate_structured` call automatically records its
   own stage (`embed`, `llm_generate`, `llm_generate_structured`) with
   timing, and `generate`'s real `LLMResponse` usage/model onto a shared
   `TraceRecorder`. Because `hybrid_search`, `generate_answer`,
   `extract_records`, and `ingest_transcript` all take an
   `EmbeddingProvider`/`LLMProvider` as a plain parameter already, passing
   in the traced decorator instead of the raw one is the entire
   integration -- **zero lines changed** in `retrieval.py`,
   `answer_generation.py`, `extraction.py`, `ingestion.py`,
   `chunking.py`, `transcript_parser.py`, or either guardrails module.
2. **`TraceRecorder.stage(name, **metadata)`**, an async context manager,
   used directly in the two router functions
   (`app/routers/ask.py:_ask`, `app/routers/meetings.py:ingest_meeting`)
   around each already-existing call to a service function
   (`hybrid_search`, `passes_retrieval_confidence`,
   `scan_chunks_for_prompt_injection`, `extract_records`,
   `add_extractions`). The router was already the orchestration layer
   composing these calls in sequence; wrapping each call site there adds
   *lines*, not new *responsibilities*, to a file whose job was already
   "call these in order."

Both seams share one `TraceRecorder` per request, so the final stage list
is a single flat, chronologically-ordered sequence. A stage that internally
triggers a provider call (e.g. `generate_answer`'s own `llm_generate` call,
which can fire twice on its internal retry -- ADR-0007) produces a nested
entry that appears *before* its enclosing stage's entry in the list, since
`TraceRecorder.stage` appends to the list on exit, and the inner
context manager exits first. This flat-list-with-natural-ordering is a
deliberate simplification over a real parent/child span tree -- see
Alternatives.

### The Trace model

```python
class TraceOutcome(StrEnum):
    ANSWERED = "answered"
    DECLINED = "declined"
    ERROR = "error"

class Trace(Base):
    id: UUID                       # doubles as the request id -- see below
    endpoint: str                  # a fixed literal, e.g. "POST /ask"
    stages: list[dict]             # JSONB -- see "Why JSONB" below
    total_duration_ms: float
    input_tokens: int
    output_tokens: int
    models_used: list[str]         # ARRAY(String), Meeting.participants' pattern
    outcome: TraceOutcome
    created_at: datetime
```

**No separate "request id" field.** A `Trace` row corresponds 1:1 to one
request; its own primary key already identifies that request uniquely.
Adding a second UUID with the same cardinality would be a field with no
distinct purpose today -- nothing else in the system needs to reference
"the request" independently of "the trace of that request."

**`endpoint` is a fixed literal per call site** (`"POST /ask"`,
`"POST /meetings/{meeting_id}/ask"`, `"POST /meetings/ingest"`), not an
interpolated path with the real `meeting_id` baked in. `GET
/traces?endpoint=` needs to group "all scoped-ask requests" together
regardless of which meeting was asked about; a literal template string is
the filterable grouping key the ROADMAP's "filterable by endpoint" asks
for, an interpolated one wouldn't be.

**`outcome` vocabulary is ask-flow vocabulary, generalized.** For the ask
flow: `answered` when `generate_answer` returns `supported=True`;
`declined` when the confidence guardrail short-circuits before any LLM
call, or when the LLM itself says `supported=False`; `error` on an
uncaught exception. For the ingest flow: `declined` has no natural
equivalent, because ADR-0008 already established that the input guardrail
(prompt-injection scanning) is *detection, not sanitization* -- ingestion
never conditionally refuses to process a transcript. Ingest traces are
therefore always `answered` (a completed ingest, whether or not it flagged
prompt injection or extracted zero decisions/action items -- both are just
data, not a different outcome) or `error`.

**`models_used` is populated even for `generate_structured` calls, whose
usage `input_tokens`/`output_tokens` are not.** `LLMResponse` (returned
only by `generate()`) is the only place token counts and the exact model
that served a call are available "for free." `generate_structured`
(extraction's only call shape) returns a validated Pydantic instance
directly, with no usage metadata at all -- a real interface gap, not
something this phase's tracing work re-derives. `TracingLLMProvider` is
constructed with `model_name` resolved from `Settings`
(`get_configured_model_name`, `app/providers/llm/factory.py`) specifically
so `models_used` is still accurate for ingest traces, even though their
token counts stay at `0`. This is documented, not silently wrong: an ingest
trace's `input_tokens`/`output_tokens` genuinely undercounts real usage,
and a reader of `eval/results` or `GET /traces` output needs to know that,
not discover it by noticing the numbers look too low.

### Why JSONB for `stages`, not a normalized table

Reusing Postgres (already required for pgvector and full-text search) and
a JSONB column for the stage list is the ROADMAP's own suggestion, and the
right call here: a trace has 3-7 stages, nothing in this system queries
*into* stage content across traces (there is no "find every trace where
the `hybrid_search` stage took over 200ms" feature requested or built), and
a `trace_stages` child table would add a second repository, a join on
every `GET /traces/{id}` read, and a migration -- for a shape that's always
read and written whole, never filtered by its own internal fields. The
GIN-indexable, queryable nature of Postgres JSONB is available later if a
real need for stage-level querying appears; nothing about this choice
forecloses it.

### Tracing starts only once real processing begins

A request that fails before any real domain work happens produces an HTTP
error but **no trace row**: an unknown `meeting_id` (404, checked before
`_ask` is even called) and a non-UTF-8 file upload (422, checked before the
`TraceRecorder` is constructed) are input-validation failures, not traced
operations. This mirrors the eval harness's own framing in ADR-0009 of
what's worth measuring versus what's just routing -- a trace should
represent an attempt at doing the thing the endpoint exists to do, not
every possible request that reached the process.

### Pagination: the first in this codebase, kept deliberately simple

`GET /traces` is the first paginated endpoint in Meridian. No existing
convention to extend, and no pagination library is a dependency
(confirmed -- none of `fastapi-pagination` or similar exists in
`pyproject.toml`). `limit`/`offset` query params (`limit` bounded to
`[1, 100]`, default `20`) plus a `total` count in the response body is the
minimal, explicit shape consistent with this codebase's existing
`Query(default=...)` filtering style (`GET /action-items?status=&owner=`).
`date` filters to one exact calendar day (UTC), matching both the
ROADMAP's literal wording ("filterable by ... date") and this codebase's
existing exact-match-only filter convention -- no range/since/until
parameters were added, since nothing currently asks for them.

## Alternatives considered

- **OpenTelemetry SDK with a real exporter** (Jaeger, Honeycomb, Datadog,
  etc.) instead of a hand-rolled `Trace` model. This is what a genuinely
  production-grade version of this system should use -- see Consequences.
  Rejected for this phase: it's real infrastructure (a collector, an
  exporter target, SDK instrumentation conventions) disproportionate to
  what a single-process demo submission needs, and the ROADMAP explicitly
  asks for a queryable API backed by Postgres, which OTel alone doesn't
  give you without also standing up a backend to query.
- **A normalized `trace_stages` table** instead of a JSONB column. Rejected
  -- see "Why JSONB" above; this is the ROADMAP's own explicit suggestion
  and the right level of engineering for data that's always read/written
  as a whole unit.
- **Decorating service functions directly**
  (`@traced("hybrid_search")` on `hybrid_search` itself, or threading a
  `TraceRecorder` parameter through `ingest_transcript`/`extract_records`
  to get independent `parse_transcript`/`chunk_turns`/store-level stages).
  Rejected: either approach touches business-logic file signatures or
  bodies, which is exactly what the ROADMAP's "without polluting business
  logic" warns against. The chosen provider-decorator + router-level
  `stage()` approach gets real stage granularity for every *provider* call
  (the actual expensive, interesting-to-measure part of both flows) with
  zero lines changed in any service module; the cost is that
  `parse_transcript`/`chunk_turns`/`MeetingRepository.create` inside
  `ingest_transcript` aren't independently staged -- they're bundled into
  one outer `ingest_transcript` span. A real, small scope trade, not an
  oversight.
- **Returning the trace/request id to the caller** (a response header, or
  a new field on `AskResponse`/`IngestResponse`). A real production system
  would likely want this for client-side correlation. Rejected for this
  phase to avoid changing Phase 3/5's already-established response
  contracts for a phase scoped to observability infrastructure, not the
  ask/ingest API surface itself. `GET /traces?endpoint=` ordered
  newest-first is how this ADR's own integration tests locate the trace a
  given request produced, and is a reasonable stand-in until/unless
  client-side correlation becomes a real requirement.
- **A true parent/child span tree** instead of a flat chronological stage
  list. Rejected as over-engineering relative to what was asked
  (`stages (list of {name, started_at, duration_ms, metadata})`, literally
  a flat list in the ROADMAP's own wording) and what's actually useful at
  this scale (3-7 stages per trace) -- the natural ordering (a stage's
  entry appears after any stage it triggered internally) already conveys
  nesting well enough to read.

## Consequences

- **What's traced**: every ask request's `embed` -> `hybrid_search` ->
  `guardrail_confidence_check` -> (`llm_generate` ->) `generate_answer`
  sequence, and every ingest request's `embed` -> `ingest_transcript` ->
  `prompt_injection_scan` -> (`llm_generate_structured` ->)
  `extract_records` -> `persist_extractions` sequence, each with real
  timing, and end-to-end latency, LLM token usage (generate() calls only),
  models used, and outcome for the request as a whole.
- **What's not traced, and why**: sub-steps inside `ingest_transcript`
  (parse/chunk/store) aren't independently staged -- see Alternatives.
  Requests that fail pure input validation (unknown `meeting_id`, non-UTF-8
  upload) produce no trace at all. `generate_structured` calls (extraction)
  always contribute `0` to `input_tokens`/`output_tokens`, a real,
  documented interface gap, not a bug to discover later by the numbers
  looking suspiciously low. A retry inside `generate_answer` or
  `extract_records` produces a second stage entry with the same name as
  the first (`llm_generate`/`llm_generate_structured`), distinguishable
  only by position in the list, not an explicit attempt-number field.
- **What this would need to become genuinely production-grade**:
  structured logs shipped to a real aggregator (ELK, Loki, CloudWatch)
  instead of a table only queryable through this app's own API; actual
  OpenTelemetry SDK instrumentation with a real exporter, so traces
  correlate across service boundaries once this stops being a single
  process; alerting on rolling aggregates (error rate, p95/p99 latency
  over a window) -- nothing computes rolling aggregates today, `GET
  /traces` only returns individual records a caller would have to
  aggregate themselves; a retention/rotation policy (`traces` grows
  unboundedly forever right now, no TTL or archival); sampling (tracing
  every single request is fine at this data volume, not at real production
  request volume); and span-level detail below "one stage per provider
  call" -- e.g. individual repository/DB-query timing, cache hits, or
  network-level retries, none of which are broken out today.
- **Pagination is offset-based**, the simplest correct choice at today's
  data volume and the first paginated endpoint in this codebase; a real
  production system at much higher trace volume would want keyset/cursor
  pagination instead, since offset pagination's cost grows with the offset
  itself -- a well-known limitation, not relevant yet at this scale.

## Links

- ADR-0002/0003 (core tech stack, ports and adapters) -- the
  `LLMProvider`/`EmbeddingProvider` interfaces this phase decorates rather
  than modifies
- ADR-0006 (chunking strategy) -- why `ingest_transcript`'s
  parse/chunk/store steps aren't independently staged
- ADR-0007 (retrieval and citation strategy) -- the ask flow instrumented
  here, and `generate_answer`'s internal retry (the source of a possible
  second `llm_generate` stage per request)
- ADR-0008 (structured extraction and guardrails) -- the ingest flow
  instrumented here, and the "detection, not sanitization" reasoning behind
  why ingest traces have no `declined` outcome
- ADR-0009 (evaluation methodology) -- the "trace real processing, not
  routing" framing this ADR reuses for the "no trace before real
  processing starts" decision
- ADR-0013 (switch default LLM to Gemini) -- why `models_used` is resolved
  from `Settings`, not introspected from the provider instance
- `ROADMAP.md` Phase 6 (observability: tracing and a traces API)
- `app/services/tracing.py`, `app/repositories/trace_repository.py`,
  `app/routers/traces.py`, `app/models/orm.py` (`Trace`, `TraceOutcome`),
  `app/providers/llm/factory.py` (`get_configured_model_name`)
- Migration `f7222b85a8b6` (add traces table)
