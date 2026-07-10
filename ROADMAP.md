# ROADMAP — Meridian Build Companion

How to use this document:

1. Open Claude Code in the repo root (make sure `CLAUDE.md` is present there
   — Claude Code reads it automatically).
2. Work through the phases in order. For each phase, copy the prompt block
   into Claude Code, let it work, review the diff yourself before accepting
   anything you don't understand, and ask it to explain anything unclear —
   that's the point, not just a courtesy.
3. Check the phase's "Definition of done" before moving on.
4. Commit and push using the suggested commit message (adjust as needed).
5. When you're done for the day, say "wrap session" in Claude Code to get
   the Obsidian notes written per `CLAUDE.md` Section 7.
6. Move to the next phase next session.

Each phase assumes the previous ones are merged and green. Do not skip
ahead if tests are red — fix forward before starting the next phase.

---

## Phase 0 — Repo bootstrap and tooling

**Goal:** empty-but-real skeleton: both apps run, lint/type-check/test
commands exist and pass on nothing, CI pipeline exists and is green on an
empty test suite, Docker Compose brings up all services.

**Why:** everything after this phase should be additive. Getting the
scaffolding, CI, and containers right first means every later phase ends
with a genuine, demonstrable commit instead of "well it works on my
machine."

**Prompt:**

```
Set up the Meridian monorepo per the layout in CLAUDE.md Section 5.

1. apps/api: FastAPI project with Python 3.12, Pydantic v2, async setup,
   pydantic-settings for config from environment variables, ruff for
   linting, mypy for type-checking, pytest + pytest-asyncio configured.
   A single health-check endpoint GET /health returning {"status": "ok"}.
   Unit test for it.

2. apps/web: Next.js (App Router) + TypeScript + Tailwind project.
   A single home page that fetches /health from the API and displays the
   status. Vitest + React Testing Library configured with one passing
   component test.

3. docker-compose.yml: postgres (with pgvector extension available),
   redis, api, web services, with a shared .env consumed via
   env_file. Everything comes up with `docker compose up` and the web
   health check page successfully calls the API.

4. .env.example at repo root listing every environment variable that will
   eventually be needed (ANTHROPIC_API_KEY, DATABASE_URL, REDIS_URL,
   EMBEDDING_PROVIDER, etc.) with one-line comments, no real values.

5. GitHub Actions workflow (.github/workflows/ci.yml) that on every push:
   lints and type-checks both apps, runs both test suites, and builds both
   Docker images. Should fail loudly and specifically if anything is
   missing rather than silently skipping steps.

6. Root README.md stub with a one-paragraph project description and a
   "more documentation coming" placeholder — do not write the real README
   yet, that's Phase 11.

Follow CLAUDE.md Section 2 (DRY, no framework magic beyond what's listed
in ADR-0002/0003) and Section 8 (definition of done) throughout. No ADR
needed for this phase, the decisions are already recorded in ADR-0002.
```

**Definition of done:**

- `docker compose up` brings up all four services with no manual steps
- CI is green on GitHub
- `pytest` and `npm test` both pass locally and in CI
- `.env.example` is complete and `.env` is gitignored

**Commit:** `chore: bootstrap monorepo, CI, and docker compose skeleton`

---

## Phase 1 — Domain modelling and seed dataset

**Goal:** the core Pydantic/SQLAlchemy models for transcripts, chunks,
decisions, and action items exist and are migrated into Postgres; a
synthetic dataset of 10-15 realistic health-tech consulting meeting
transcripts exists in `data/transcripts/`.

**Why:** everything downstream (chunking, retrieval, extraction) needs a
settled schema and real data to develop against, not mocks.

**Prompt:**

```
Read ADR-0001 and ADR-0002 before starting.

1. Design SQLAlchemy models (with Alembic migrations) for:
   - Meeting (id, title, date, participants, source_filename, raw_text)
   - Chunk (id, meeting_id FK, speaker, start_ts, end_ts, text, embedding
     vector column via pgvector, chunk_index)
   - Decision (id, meeting_id FK, text, source_chunk_id FK, confidence)
   - ActionItem (id, meeting_id FK, text, owner, due_date nullable,
     source_chunk_id FK, confidence, status)

   Write the corresponding Pydantic schemas for API request/response
   shapes, kept separate from the ORM models (no leaking ORM objects
   through the API layer).

2. Write a short ADR (docs/adr/0005-domain-schema.md, using the template)
   for any non-obvious modelling choice you make (e.g. why confidence is
   stored per-decision, why source_chunk_id is required not optional).

3. Generate a synthetic dataset: 10-15 plain-text transcripts in
   data/transcripts/, speaker-labelled and timestamped, e.g.:

   [00:03:12] Dhruvisha: I think we should lock the WorkoutFeedback schema
   before the next sprint.

   Simulate a health-tech consulting engagement: a mix of stakeholder
   discovery calls, sprint reviews, and a couple of clinical-advisory-style
   meetings, with genuine decisions and action items embedded naturally in
   the dialogue (not artificially labelled — the extraction system has to
   find them later). Vary meeting length and speaker count realistically.

4. A loader script/test fixture that inserts one sample transcript end to
   end (meeting row + placeholder chunks, no embeddings yet — that's
   Phase 2) to prove the schema round-trips.

Follow CLAUDE.md throughout — tests for the models and the loader,
migration is idempotent and reversible.
```

**Definition of done:**

- Migrations apply cleanly on a fresh database
- Sample transcript round-trips through the loader with a passing test
- ADR-0005 exists if any schema decision warranted it
- 10-15 transcripts exist and read like real meetings, not lorem ipsum

**Commit:** `feat: domain schema, migrations, and synthetic transcript dataset`

---

## Phase 2 — Ingestion pipeline: parse, chunk, embed, store

**Goal:** a working pipeline that takes a raw transcript file and produces
embedded, stored chunks.

**Why:** this is the first assignment checkpoint the README has to justify
explicitly — chunking strategy and embedding model choice.

**Prompt:**

```
Read ADR-0003 and ADR-0004 before starting.

1. Implement a transcript parser: speaker-labelled, timestamped plain text
   -> a list of speaker turns with start/end timestamps. Handle turns that
   span multiple lines. Write unit tests against a few hand-crafted edge
   cases (turn with no timestamp, consecutive turns from the same speaker,
   a malformed line) — document any format you deliberately don't support
   in a comment, don't silently swallow it.

2. Implement chunking: speaker-turn-aware — a chunk never splits mid-turn
   unless a single turn exceeds a configurable max token length, in which
   case split on sentence boundaries within that turn. Unit test the
   boundary behaviour directly (a turn just under, just at, and just over
   the limit).

3. Implement EmbeddingProvider per ADR-0004: a LocalBGEEmbeddingProvider
   using sentence-transformers as the default, behind the EmbeddingProvider
   interface, with a VoyageEmbeddingProvider (or OpenAI) as an alternate
   implementation selected via the EMBEDDING_PROVIDER env var. Unit test
   the interface contract with a fake provider; integration test the real
   local provider against a couple of known sentences (e.g. cosine
   similarity of two paraphrases should exceed similarity of two unrelated
   sentences — a real assertion, not just "it returns a vector").

4. Wire ingestion end to end: POST /meetings/ingest accepting a transcript
   file, running parse -> chunk -> embed -> store, returning the created
   Meeting id and chunk count. Integration test against a real sample
   transcript, asserting the right number of chunks land in the DB.

5. Write docs/adr/0006-chunking-strategy.md documenting the speaker-turn-
   aware approach and why (with the specific trade-off: fixed-size chunking
   would be simpler but breaks conversational context; the actual approach
   taken and its cost).
```

**Definition of done:**

- A real transcript file, POSTed to /meetings/ingest, produces chunks with
  embeddings in the database
- Chunking boundary tests pass
- EmbeddingProvider is swappable via env var, verified by a test using a
  fake provider
- ADR-0006 exists

**Commit:** `feat: transcript ingestion pipeline (parse, chunk, embed, store)`

---

## Phase 3 — Retrieval and RAG question-answering with citations

**Goal:** POST /meetings/ask (or per-meeting/global, your call — write the
ADR either way) that retrieves relevant chunks and generates a cited
answer.

**Why:** this is the core "answers questions using RAG" requirement from
the assignment's "What We're Looking For."

**Prompt:**

```
1. Implement retrieval: cosine similarity search over pgvector, combined
   with Postgres full-text search (tsvector) on chunk text, fused with a
   simple weighted score (not a full cross-encoder re-ranker — note this
   trade-off in an ADR). Unit test the fusion scoring logic directly with
   synthetic scores, not just end to end.

2. Implement the answer-generation step via LLMProvider (Claude): given a
   question and the top-k retrieved chunks, generate an answer that must
   cite which chunk(s) it drew from (chunk id + timestamp). Enforce the
   citation via response schema validation — if the model's response
   doesn't include valid citations to chunks that were actually retrieved,
   treat it as a guardrail failure (see Phase 4) and retry once with a
   stricter instruction before surfacing a "could not find a well-
   supported answer" response to the user.

3. POST /meetings/{id}/ask and a global POST /ask across all meetings.
   Integration tests: a question with a clear answer in a known sample
   transcript should return that answer with a citation pointing at the
   correct chunk; a question with no relevant content anywhere should
   trigger the "not well-supported" path, not a hallucinated answer.

4. Write docs/adr/0007-retrieval-and-citation-strategy.md covering the
   hybrid search choice, top-k value chosen and why, and the citation
   enforcement approach.
```

**Definition of done:**

- Asking a question with a known answer in the seed data returns the
  correct answer with a correct citation
- Asking an out-of-scope question returns the "not well-supported"
  response, not a fabricated one
- ADR-0007 exists

**Commit:** `feat: hybrid retrieval and cited RAG question-answering`

---

## Phase 4 — Structured extraction and guardrails

**Goal:** decisions and action items are extracted automatically at
ingestion time and stored relationally; basic guardrails are enforced
across the whole pipeline.

**Why:** this is what separates Meridian from a plain document-QA bot, and
it's a named assignment checkpoint (Guardrails, Quality Controls).

**Prompt:**

```
1. Implement structured extraction via Claude tool-calling / structured
   output: given a meeting's chunks, extract Decision and ActionItem
   records (text, owner if named, due date if named, confidence,
   source_chunk_id). Run this as part of the ingestion flow from Phase 2
   (after chunking/embedding, before returning the ingest response).
   Integration test against a seed transcript with a known decision and a
   known action item embedded in the dialogue — assert both are extracted
   correctly with the right source chunk linked.

2. Implement guardrails as a distinct, testable module (not scattered
   inline checks):
   - Input guardrail: scan uploaded transcript text for prompt-injection-
     style content (e.g. instructions addressed to an AI model embedded in
     the transcript text) before it is ever included in a prompt. Flag,
     don't silently strip — surface the flag in the ingest response.
   - Output guardrail: the citation-enforcement from Phase 3, plus a
     confidence threshold below which the system declines to answer rather
     than guessing.
   - Optional PII consideration: document in the ADR whether/why you did
     or didn't implement redaction for this submission, given the
     health-adjacent synthetic data.

   Unit test each guardrail directly with crafted inputs designed to
   trigger it and inputs designed to pass cleanly.

3. GET /meetings/{id}/decisions and GET /meetings/{id}/action-items
   endpoints, plus a global GET /action-items with basic filtering
   (by status, by owner).

4. Write docs/adr/0008-structured-extraction-and-guardrails.md.
```

**Definition of done:**

- A seed transcript with an obvious decision and action item produces
  correctly extracted, correctly linked records
- Guardrail unit tests cover both trigger and pass-through cases
- ADR-0008 exists

**Commit:** `feat: structured decision/action-item extraction and guardrails`

---

## Phase 5 — Evaluation harness wired into CI

**Goal:** a golden dataset of Q&A pairs with known expected supporting
chunks, an eval script that scores retrieval quality and uses Claude as an
LLM-judge for answer faithfulness/relevance, and a CI gate that fails the
build if quality regresses below a threshold.

**Why:** this is the "Quality Controls" and "AI Evaluation & Observability"
checkpoint, and it's the single most senior-looking thing in this
submission if done well.

**Prompt:**

```
1. Build eval/golden_dataset/: 15-20 hand-written question/expected-answer/
   expected-supporting-chunk-id triples against the seed transcripts,
   covering: direct-fact questions, decision questions, action-item
   questions, and at least 2-3 deliberately out-of-scope questions that
   should trigger the "not well-supported" guardrail response.

2. Build eval/run_eval.py:
   - Retrieval metrics: precision@k and recall@k against the expected
     supporting chunk for each golden question.
   - LLM-as-judge: for each generated answer, ask Claude (a separate,
     clearly-labelled judge call, not the same call that generated the
     answer) to score faithfulness (is every claim supported by the cited
     chunks) and relevance (does it actually answer the question) on a
     simple rubric, 1-5.
   - Aggregate and print a report; write it to eval/results/latest.json.

3. Add an eval CI job: run the eval suite and fail the build if mean
   retrieval recall@k or mean faithfulness score drops below a threshold
   you choose and justify. This is a real quality gate, not a report
   nobody reads.

4. Write docs/adr/0009-evaluation-methodology.md covering: why this metric
   set, why LLM-as-judge instead of only retrieval metrics, the threshold
   values chosen and why, and the acknowledged limitation that a
   20-question golden set is a directional signal, not statistically
   rigorous — and what a production-scale eval set would need to look like.
```

**Definition of done:**

- `python eval/run_eval.py` runs locally and produces a report
- The CI eval gate is wired in and actually fails on a deliberately broken
  build (verify this once, then fix it back)
- ADR-0009 exists

**Commit:** `feat: golden-dataset evaluation harness with LLM-judge, wired into CI`

---

## Phase 6 — Observability: tracing and a traces API

**Goal:** every ask/extraction request produces a structured trace record
(stages, latencies, tokens, retrieval scores, model used) queryable via an
API, ready for the frontend traces dashboard in Phase 7.

**Why:** named assignment checkpoint (Observability), and a strong visual
differentiator once it has a UI.

**Prompt:**

```
1. Implement a Trace model: request id, endpoint, stages (list of {name,
   started_at, duration_ms, metadata}), total latency, token counts,
   model(s) used, outcome (answered / declined / error). Instrument the
   Phase 3 ask flow and Phase 2/4 ingestion+extraction flow to record a
   trace for every call, without polluting business logic — a decorator
   or context manager, not inline timing calls scattered through services.

2. Persist traces (reuse Postgres; a JSONB column for the stage list is
   fine here — note this choice, don't over-normalize it).

3. GET /traces (paginated, filterable by endpoint/outcome/date) and
   GET /traces/{id} for the full detail. Integration test that asking a
   question produces a retrievable trace with the expected stages present.

4. Write docs/adr/0010-observability-approach.md: what's traced, what
   isn't (and why), and what this would need to become to be genuinely
   production-grade (structured logs to a real aggregator, OpenTelemetry
   export, alerting) versus what was reasonable to build for this
   submission.
```

**Definition of done:**

- Every ask and ingest call produces a queryable trace with real stage
  timings, not stubbed data
- ADR-0010 exists

**Commit:** `feat: request tracing and traces API`

---

## Phase 7 — Frontend: chat, decisions/action-items, and traces dashboard

**Goal:** the actual product surface — glass/neumorphic design system per
CLAUDE.md Section 3, a chat interface for asking questions with visible
citations, a decisions/action-items timeline view, and a traces dashboard.

**Why:** this is where "creativity in UI/UX and product innovation" gets
judged directly.

**Prompt:**

```
Read CLAUDE.md Section 3 before starting. This phase is UI-heavy; keep
components small and composable, colocate tests with components.

1. Design system: a small set of base components (Panel, Card, Button,
   Badge, Input) implementing the glass/neumorphic language — translucent
   blurred panels, soft shadows, one restrained accent colour, no neon,
   no emoji anywhere in copy. Component tests for rendering and basic
   interaction, not visual regression (out of scope here).

2. Chat view: ask a question (global or scoped to a meeting), show the
   streamed answer, and render citations as clickable chips that reveal
   the source chunk (speaker, timestamp, text) inline. Handle and clearly
   display the "not well-supported" guardrail response distinctly from a
   normal answer.

3. Decisions & action items view: a per-meeting timeline (chronological by
   timestamp) showing extracted decisions and action items, each linked
   back to its source citation, with filtering by owner/status for action
   items.

4. Traces dashboard: a list of recent requests (endpoint, outcome,
   latency, token count) with a detail view showing the stage-by-stage
   timeline from Phase 6 — this is the observability story made visible.

5. Playwright e2e test covering the primary happy path: ingest a
   transcript (or use seeded data), ask a question, see a cited answer,
   view the decisions/action-items for that meeting, view its trace.
```

**Definition of done:**

- All three views work against the real backend, not mocked data
- The design reads as calm, minimal, trustworthy — not templated Bootstrap
  defaults, not neon, no emoji
- The Playwright happy-path test passes in CI

**Commit:** `feat: chat, decisions/action-items, and traces UI`

---

## Phase 8 — MCP server exposure

**Goal:** an MCP server exposing search/ask (and optionally extraction
lookup) as tools, runnable from Claude Code or Claude Desktop.

**Why:** the JD explicitly lists "experience building applications
involving MCPs" — almost no other candidate's submission will have this.

**Prompt:**

```
1. Build a small MCP server (Python, using the official MCP SDK) exposing
   tools: search_meetings(query, top_k), ask_meetings(question,
   meeting_id optional), get_action_items(status, owner optional). Each
   tool calls the existing FastAPI backend rather than duplicating logic
   — the MCP server is a thin adapter, not a second implementation.

2. Document how to register it with Claude Desktop/Claude Code
   (mcp config snippet) in the README's setup section (flag this for
   Phase 11, but write the actual config now while it's fresh).

3. A basic smoke test: invoke each tool against a running backend and
   assert a well-formed response.

4. Write docs/adr/0011-mcp-exposure.md: what it's for, why exposing the
   backend as MCP tools rather than only a REST API adds value (e.g. an
   FDE could query past client meetings directly from their own AI coding
   assistant while working), and what's out of scope (no MCP-side auth for
   this submission — noted as a real gap for production).
```

**Definition of done:**

- The MCP server runs and its tools work against the real backend
- ADR-0011 exists

**Commit:** `feat: expose search/ask/action-items as MCP tools`

---

## Phase 9 — Testing hardening and CI/CD finalization

**Goal:** close coverage gaps, make CI the real gatekeeper it should be.

**Prompt:**

```
1. Run coverage reports for both apps. Identify any untested branch in
   business logic (chunking, retrieval fusion, extraction, guardrails,
   tracing) — trivial code (simple getters, framework boilerplate) does
   not need tests, but no business-logic branch should be uncovered.
   Fill the real gaps.

2. Ensure CI runs, in order, and fails fast on: lint, type-check, unit
   tests, integration tests, eval-suite gate, then builds and tags Docker
   images on success. Add a status badge to the README stub.

3. Do a full docker compose up from a clean checkout (no cached state) and
   confirm the whole system works end to end with just .env populated from
   .env.example plus a real ANTHROPIC_API_KEY. Fix anything that only
   worked because of leftover local state.
```

**Definition of done:**

- Coverage report shows no untested business-logic branch
- A clean-checkout `docker compose up` works with only one API key set
- CI badge is green

**Commit:** `test: close coverage gaps; chore: finalize CI/CD pipeline`

---

## Phase 10 — Voice-to-transcript, with real speaker diarization

**Goal:** full audio-to-transcript ingestion, including genuine speaker
diarization, not transcription-only. This is a first-class feature, not a
stretch goal — treat it with the same rigour as Phases 1-9.

**Why:** the bonus is named in the brief, and most candidates who attempt
it at all will do transcription without diarization, or fake speaker
labels. Doing it properly — real diarization, honestly evaluated — is a
genuine differentiator and a legitimate excuse to show a second, distinct
ML pipeline (audio) alongside the text/RAG pipeline. It's still sequenced
after Phase 9 on purpose: build order matters independent of time
available — a second complex pipeline is easier to get right once the
foundation it feeds into is stable and tested, not before.

**Prompt:**

```
Add an audio ingestion path: POST /meetings/ingest-audio accepting an
audio file, running it through:

1. Transcription: local faster-whisper (or an API-based Whisper — pick
   one, write the ADR either way) producing timestamped text segments.

2. Speaker diarization: pyannote.audio (or an equivalent diarization
   pipeline) producing speaker-attributed time segments, aligned against
   the transcription segments to produce genuinely speaker-labelled,
   timestamped turns — not hardcoded or manually assigned labels.

3. Feed the aligned, diarized transcript into the existing Phase 2
   ingestion pipeline unchanged (parse -> chunk -> embed -> store;
   extraction, guardrails, and tracing all apply automatically since the
   output format matches what Phase 2 already consumes).

Handle the realistic edge cases directly rather than hand-waving them:
overlapping speech, a diarization pass that produces more or fewer
speakers than the true count, and short utterances that are hard to
attribute confidently. Decide and implement a policy for each — e.g.
below-confidence-threshold segments get an explicit "unknown speaker"
label rather than a guessed one.

Write integration tests against at least one real (or realistically
constructed) multi-speaker audio sample, asserting: transcription content
is reasonable, speaker turns are attributed, and the resulting Meeting/
Chunk records are the same shape as a text-ingested meeting.

Write docs/adr/0012-voice-to-transcript-and-diarization.md documenting
the transcription and diarization stack chosen, how the two model
outputs are aligned, the edge-case policies above, and an honest
statement of diarization's real-world error rate on your test sample —
not a claim that it's flawless.
```

**Definition of done:**

- A real multi-speaker audio file, uploaded via /meetings/ingest-audio,
  produces a Meeting with correctly diarized, chunked, and embedded
  records — indistinguishable downstream from a text-ingested meeting
- Overlap and low-confidence-attribution policies are implemented and
  tested, not just described
- ADR-0012 exists and states measured diarization accuracy honestly

**Commit:** `feat: audio ingestion with transcription and speaker diarization`

---

## Phase 11 — README, architecture diagram, screenshots, submission polish

**Goal:** the actual submission artifact.

**Why:** re-read CLAUDE.md Section 10 before starting this phase. The
README's decision/reflection sections must be rewritten by TJ personally,
not shipped as Claude's draft.

**Prompt:**

```
Draft (draft only — TJ will rewrite the reflective sections) a README.md
covering, in this order, matching the assignment's exact requested
structure:

1. Quick setup instructions (docker compose up, required .env values)
2. Architecture overview, with a simple diagram (ASCII or a Mermaid
   diagram is fine) showing: web -> api -> {postgres+pgvector, redis,
   Anthropic API} plus the MCP server as a peer client of the API, plus
   the audio ingestion path (faster-whisper + diarization) feeding into
   the same downstream pipeline as text ingestion.
3. What would be required to productionize this and deploy it on a
   hyperscaler: reference the Terraform sketch, discuss what's stubbed vs
   real, discuss the pgvector -> dedicated vector DB scaling trigger from
   ADR-0004, discuss auth/multi-tenancy as an explicit current gap.
4. RAG/LLM approach and decisions: summarise ADR-0002 through ADR-0004 and
   0006-0007 in plain language, don't just link them.
5. Key technical decisions and why: pull from all ADRs.
6. Engineering standards followed, and what was consciously skipped (be
   honest about the non-goals in CLAUDE.md Section 9).
7. How AI coding tools were used in development (this section in
   particular is TJ's to write, not Claude's).
8. What would be done differently with more time.
9. Screenshots (leave placeholders for TJ to drop in real screenshots of
   the running app; list exactly which screens to capture: chat with
   citation, decisions/action-items timeline, traces dashboard).

Also draft docs/adr/README.md, a one-page index listing every ADR by
number and one-line title, for easy navigation by a reviewer.
```

Once drafted, TJ personally rewrites sections 4-8 in his own words before
this is submitted anywhere. This is the last phase — after this, say
"wrap session" for a final set of notes, then the assignment is ready to
send.

**Definition of done:**

- README matches the assignment's requested structure exactly
- Screenshots are real, not placeholders, in the final version
- Sections 4-8 read like TJ wrote them, because he did
- ADR index exists and is accurate

**Commit:** `docs: finalize README and ADR index for submission`
