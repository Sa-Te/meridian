# CLAUDE.md — Meridian (Newpage FDE Take-Home)

This file is the standing contract between TJ and Claude Code for this repository.
Read it in full before touching any code. It does not get superseded by anything
in chat unless TJ explicitly says so in that session.

## 1. What this project is

Meridian is a meeting intelligence system: it ingests meeting transcripts
(speaker-labelled, timestamped text) from a simulated health-tech consulting
engagement, and answers questions about discussions, decisions, and action
items using retrieval-augmented generation. It is being built as the take-home
assignment for a Forward Deployed Engineer role at Newpage Solutions, and it
is also TJ's first serious production-grade RAG system, built to learn from,
not just to ship.

Both goals matter equally. Every phase should leave TJ able to explain, in his
own words, what was built and why — not just able to point at working code.

## 2. Non-negotiable engineering principles

- **DRY and single-responsibility.** No copy-pasted logic between ingestion,
  retrieval, and extraction. Shared logic lives in one place and is imported.
- **Ports and adapters for anything that might change vendors.** LLM calls,
  embedding calls, and vector search go through an interface
  (`LLMProvider`, `EmbeddingProvider`, `VectorStore`). Concrete implementations
  are swappable via config/env, never hardcoded into business logic.
- **Tests are not optional and not an afterthought.** Every new module gets
  unit tests in the same PR/commit that introduces it. Integration tests cover
  every API endpoint. Target is full meaningful coverage of business logic —
  not 100% of trivial getters, but no untested branch in chunking, retrieval,
  extraction, or guardrail logic.
- **No framework magic without justification.** LangChain/LlamaIndex-style
  orchestration frameworks are not used for the core pipeline (see
  `docs/adr/0003`). Every retrieval and generation step should be code TJ can
  read start to finish and explain live in an interview.
- **Readability over cleverness.** If a reviewer (human or TJ six months from
  now) needs more than the docstring to understand a function, the function
  is too clever.
- **No emojis.** Not in code, not in comments, not in docs, not in ADRs, not
  in commit messages, not in the UI copy.
- **No secrets in the repo, ever.** All credentials via `.env`, which is
  gitignored. Commit `.env.example` with dummy values and a comment per key.
- **Every non-trivial decision gets an ADR before or immediately after the
  code that implements it lands.** See Section 6.

## 3. Design language (frontend)

Glass / neumorphic minimalism. Concretely:

- Frosted, translucent panels (`backdrop-filter: blur`) over a soft, muted
  background gradient — not pure white, not black, not neon.
- Soft, low-contrast shadows for depth (neumorphic edges), not hard drop
  shadows or glow effects.
- One accent colour used sparingly (a muted teal or deep blue reads as
  clinical/trustworthy, which fits the health-tech framing) — everything else
  is near-monochrome greys.
- Generous whitespace, typography-led hierarchy over colour-led hierarchy.
- No gradients-as-decoration, no gratuitous animation, no emoji anywhere in
  copy, empty states, or tooltips.
- Every screen should look like it belongs in a product a hospital
  procurement team would trust, not a hackathon demo.

Reference `docs/adr/` for anything design-adjacent that becomes a real
decision (e.g. component library choice) — log it.

## 4. Fixed tech stack

Decided and recorded in `docs/adr/0002-core-tech-stack.md`. Do not deviate
without writing a new ADR first. The LLM line below reflects
`docs/adr/0013-switch-default-llm-to-gemini.md`, which supersedes ADR-0002's
original Anthropic-default choice; everything else in this list is still
ADR-0002 as originally decided.

- Frontend: Next.js (App Router), TypeScript, Tailwind, component tests with
  Vitest + React Testing Library, e2e with Playwright.
- Backend: FastAPI, Python 3.12, Pydantic v2, async throughout, pytest.
- Storage: PostgreSQL with `pgvector` for both relational and vector data;
  Redis for caching and lightweight rate limiting.
- LLM: Gemini (`gemini-3.1-flash-lite` by default) for generation and, for
  now, the eval LLM-judge — the sole active default `LLMProvider`, and the
  only external API key (`GEMINI_API_KEY`) required to run the system end to
  end. `AnthropicLLMProvider` remains in the codebase as a second, inactive
  implementation of the same interface (`LLM_PROVIDER=anthropic`), proving
  the abstraction works, but no code path may assume `ANTHROPIC_API_KEY` is
  set. See `docs/adr/0013` for the cost reasoning, the free-tier trade-offs,
  and the known self-preference-bias limitation of judging Gemini's output
  with Gemini.
- Embeddings: local open-source model (`BAAI/bge-base-en-v1.5` via
  `sentence-transformers`) by default, so the only external API key required
  to run the whole system end-to-end is `GEMINI_API_KEY`. Voyage AI or
  OpenAI embeddings are supported as a config swap for higher-recall
  production use — see `docs/adr/0004`.
- Orchestration: custom, thin, hand-written pipeline. No LangChain/LlamaIndex.
- Containerization: Docker Compose for local/dev; a Terraform sketch under
  `infra/terraform/` documents (does not necessarily deploy) an AWS path.
- CI: GitHub Actions — lint, type-check, unit + integration tests, then build
  + tag images, on every push (`.github/workflows/ci.yml`). The eval-suite
  gate runs in a separate workflow (`.github/workflows/eval.yml`), on push
  to `main` and manual `workflow_dispatch` only, not on every push — see
  `docs/adr/0016` for why (free-tier Gemini quota exhaustion) and
  `docs/adr/0015` for the coverage-tooling and fail-fast ordering work that
  preceded it.

## 5. Repository layout

```
apps/
  web/            Next.js frontend
  api/            FastAPI backend
    app/
      routers/    thin HTTP layer
      services/   business logic (chunking, retrieval, extraction, guardrails)
      providers/  LLMProvider / EmbeddingProvider / VectorStore adapters
      models/     Pydantic schemas + SQLAlchemy models
      repositories/  DB access, one per aggregate
    tests/
      unit/
      integration/
  mcp_server/     MCP server exposing search/ask/action-items as tools
                  (Phase 8, docs/adr/0011) -- a thin HTTP client of
                  apps/api, no business logic of its own
    mcp_server/
    tests/
eval/
  golden_dataset/ Q&A pairs with expected supporting chunks
  run_eval.py     retrieval + LLM-judge scoring, used in CI
infra/
  terraform/      AWS sketch (ECS, RDS+pgvector, ElastiCache, S3, ALB)
docs/
  adr/            architecture decision records
  screenshots/
data/
  transcripts/    synthetic sample transcripts for the demo dataset
CLAUDE.md
ROADMAP.md
README.md
docker-compose.yml
```

## 6. ADR workflow (mandatory)

Before implementing anything that fits one of these categories, write an ADR
in `docs/adr/` using `docs/adr/0000-template.md`, numbered sequentially:

- Choice of library, framework, or external service
- Data model or schema shape for a new domain concept
- A trade-off between two reasonable approaches
- Anything the assignment README explicitly asks TJ to justify (chunking,
  embedding model, vector DB, orchestration, guardrails, quality, observability)

If Claude Code makes a decision inline while coding and only realizes
afterward it was ADR-worthy, write the ADR immediately after, don't skip it.
Session notes (Section 7) reference ADRs by number; keep numbering
consistent.

## 7. Session Notes (Obsidian) — Triggered Behaviour

When TJ says any of: **"wrap session"**, **"log notes"**, **"we are done
now, log everything into notes"**, or a clear equivalent — generate
structured notes and write them to the Obsidian vault (NOT the repo).

### Folder structure

| Content                                                  | Folder (absolute WSL path)                                         | Filename format            |
| --------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------- |
| Session summary, concepts learned, bugs fixed, decisions | `/mnt/c/Users/Asuna/Documents/InstaVault/Meridian/learning-notes/`  | `YYYY-MM-DD_session-NN.md` |
| Architecture diagrams (text), structural design notes    | `/mnt/c/Users/Asuna/Documents/InstaVault/Meridian/architecture/`    | `YYYY-MM-DD_<topic>.md`    |
| Bug investigations — symptom, cause, fix, lesson         | `/mnt/c/Users/Asuna/Documents/InstaVault/Meridian/debug-log/`       | `YYYY-MM-DD_<bug-slug>.md` |
| Mind-maps (nested bullet outlines of concepts)           | `/mnt/c/Users/Asuna/Documents/InstaVault/Meridian/mind-maps/`       | `YYYY-MM-DD_<topic>.md`    |

(Rename `Meridian` in these paths if the project ends up named differently —
the structure matters, not the label.)

### Rules

- **Always** write a session note to `learning-notes/` on every triggered wrap.
- If architecture decisions were made → **also** write a file to `architecture/`.
- If non-trivial bugs were fixed → **also** write a file to `debug-log/`.
- If a concept is complete enough to summarise → **also** write a file to `mind-maps/`.
- **Never dump everything into one file.** Separate files, separate folders, separate purposes.
- Do NOT write session notes unless triggered.
- Do NOT put any of these files in the repo.

### Linking rules (for graph view)

Every note must link to related concepts using Obsidian wikilinks `[[like this]]`.

- Session notes must link to any concept, architecture decision, or bug that
  came up: e.g. `[[speaker-turn-chunking]]`, `[[pgvector]]`, `[[ADR-0004]]`.
- When a new concept appears for the first time, create a small standalone
  **concept note** in `learning-notes/concepts/` — title, one-paragraph
  definition, links to related concepts. Filename: `<concept-name>.md`.
- Architecture notes must link back to their ADR: e.g. `[[0004-vector-storage-and-embedding-provider]]`.
- Debug logs must link to the file or concept where the bug lived.
- Mind-maps must link every bullet that has a concept note.

### Session note structure (`learning-notes/`)

```
# Session NN — YYYY-MM-DD

## What we worked on
## What we built / changed
## Concepts learned
## Logic & flow
## Open questions / TODO next session
```

### Architecture note structure (`architecture/`)

```
# <Topic> — YYYY-MM-DD

## What was decided
## Why (the reasoning)
## Trade-offs
## How it fits the system
```

### Debug log structure (`debug-log/`)

```
# <Bug slug> — YYYY-MM-DD

## Symptom
## Root cause
## Fix
## Lesson
```

### Mind-map structure (`mind-maps/`)

```
# <Topic> — YYYY-MM-DD

- Main concept
  - Sub-concept
    - Detail
```

Keep all notes educational, specific to what actually happened, and written
as if teaching a smart beginner. These are TJ's personal knowledge base.

## 8. Definition of done, per phase

A phase in `ROADMAP.md` is done only when:

1. All new code has unit + (where applicable) integration tests, and the
   full suite passes.
2. Lint and type-check are clean (`ruff`, `mypy`, `eslint`, `tsc --noEmit`).
3. Any ADR-worthy decision made during the phase has a written ADR.
4. The change is committed with a conventional commit message
   (`feat:`, `fix:`, `test:`, `docs:`, `chore:`) and pushed to `main`
   (or the phase's branch, merged and pushed). No `Co-Authored-By` trailer
   on any commit, regardless of how much of the change Claude Code wrote --
   commits in this repo are attributed to TJ only.
5. TJ has been walked through what changed and why, in plain language,
   before moving to the next phase.

## 9. Explicit non-goals for this assignment

- No multi-tenant auth system. A single-user local/dev experience is enough;
  note the gap in the README's "what I'd do differently" section.
- No horizontal scaling infrastructure actually stood up. Terraform is a
  documented sketch, not a live deployment, unless TJ decides otherwise.
- No exhaustive edge-case handling for malformed transcript formats — acknowledge
  known gaps in the README rather than gold-plating parsing logic.
- Voice-to-transcript (Phase 10) is a full feature with real speaker
  diarization, not transcription-only. It is still sequenced after the
  core text pipeline is hardened (Phase 9), because a second complex
  pipeline is easier to get right once the foundation it feeds is stable
  — that ordering holds regardless of how much time is available.

## 10. On AI-assisted development and the README

The assignment explicitly says: *"We need your thoughts, not an LLM's direct
output."* This matters more than any other line in the brief. Claude Code
can draft the README, but before submission TJ must personally rewrite, in
his own voice:

- Key technical decisions and why (can start from the ADRs, but restate them
  personally, not paste them)
- Engineering standards followed, and what was consciously skipped
- How AI coding tools were used, and the do's/don'ts TJ actually applied
- What TJ would do differently with more time

Claude Code should flag this requirement again at Phase 11 (README) rather
than just writing a polished README and calling it finished.
