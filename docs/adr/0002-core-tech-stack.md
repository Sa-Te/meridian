# ADR-0002: Core tech stack

Status: Accepted
Date: 2026-07-10

> **Amendment (2026-07-10):** the LLM choice below (Anthropic Claude as
> default) is superseded by [ADR-0013](0013-switch-default-llm-to-gemini.md),
> which switches the default `LLMProvider` to Gemini for cost reasons.
> Everything else in this ADR (frontend/backend/storage/CI stack, and the
> provider-abstraction reasoning it rests on) still stands.

## Context

The assignment says "you decide the tech stack" and explicitly states the
reviewers care about reasoning over stack choice itself. Separately, the
target JD names a specific stack almost line for line: Python and
JavaScript/TypeScript with Next.js across backend and frontend, AWS
(Cloudflare also valued), Terraform/CloudFormation, PostgreSQL plus a
document store and Redis, GitHub Actions, and fluency with AI coding tools.

## Decision

- Frontend: Next.js (App Router) + TypeScript + Tailwind.
- Backend: FastAPI + Python 3.12 + Pydantic v2, fully async.
- Storage: PostgreSQL with the `pgvector` extension serving both relational
  and vector storage in a single instance; Redis for caching and rate
  limiting.
- LLM: Anthropic Claude, used for generation, structured extraction, and as
  the LLM-judge in the evaluation harness.
- Containerization: Docker Compose for local development; a Terraform
  sketch under `infra/terraform/` for the AWS productionization path.
- CI: GitHub Actions.

## Alternatives considered

- **Separate dedicated vector database (Pinecone/Qdrant/Weaviate).**
  Rejected as the default for this submission's scale — the assignment
  explicitly rewards a well-engineered basic solution over an
  over-engineered complex one, and pgvector inside the existing Postgres
  instance covers the corpus size a meeting-transcript demo actually needs.
  Documented in ADR-0004 as the point at which a dedicated vector DB would
  become justified.
- **MongoDB or another document store**, to literally tick the JD's
  "document databases" line. Rejected as unjustified complexity: transcripts
  are stored as flat files (locally, or object storage in the productionized
  path), which already plays the role a document store would play here.
  Reasoning is written out explicitly in the README rather than adding
  infrastructure with no real job to do.
- **OpenAI models** instead of Claude. Viable and kept available behind the
  `LLMProvider` interface, but not the default — building with Claude Code
  while generating with the Claude API keeps the tool-use, structured
  output, and prompt-caching story coherent for the technical interview.

## Consequences

- Single-vendor dependency for core generation (Anthropic) — mitigated by
  the provider abstraction, so a swap is a config change, not a rewrite.
- Postgres/pgvector performance at scale (millions of chunks) is a real
  limitation, documented explicitly in the "how would you productionize
  this" section of the README rather than solved prematurely.

## Links

- ADR-0003 (orchestration approach)
- ADR-0004 (vector storage and embedding provider)
- ADR-0013 (supersedes the LLM default choice above)
