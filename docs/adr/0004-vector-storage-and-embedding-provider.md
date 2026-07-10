# ADR-0004: Vector storage and embedding provider

Status: Accepted
Date: 2026-07-10

## Context

The assignment asks explicitly for the embedding model and vector database
choice, with reasoning, in the README. Anyone reviewing this repo needs to
be able to clone it and run it with minimal friction; every extra required
API key is a point of friction (and cost) for a reviewer who is evaluating
many submissions.

## Decision

- **Vector store:** `pgvector` inside the same PostgreSQL instance already
  used for relational data (transcripts, chunks, decisions, action items,
  eval results). No dedicated vector database for this submission.
- **Embedding model:** a local, open-source model
  (`BAAI/bge-base-en-v1.5`, served via `sentence-transformers` inside the
  API container) as the default, so the entire system runs end-to-end with
  a single external credential (`ANTHROPIC_API_KEY`). The `EmbeddingProvider`
  interface makes Voyage AI or OpenAI embeddings a one-environment-variable
  swap for anyone who wants higher-recall production embeddings.

## Alternatives considered

- **Voyage AI embeddings as the default.** Anthropic's recommended embedding
  partner, and likely higher retrieval quality than a local model.
  Rejected as the *default* specifically because it would require a second
  paid API key just to run the demo, which is real friction for a reviewer
  and an unnecessary cost for a take-home. Kept as the documented
  higher-quality swap-in.
- **Dedicated vector database (Qdrant, Pinecone, Weaviate).** Better ANN
  index options and horizontal scaling story, but unjustified for a
  transcript corpus of this size, and adds an extra moving part to
  `docker-compose.yml` with no real job to do yet. The README's
  productionization section states the concrete trigger for revisiting
  this: corpus size past roughly a few million chunks, or a need for
  per-tenant index isolation.
- **OpenAI embeddings.** Similar quality/friction trade-off to Voyage;
  supported behind the same interface, not the default, for the same
  single-API-key reasoning.

## Consequences

- Local embedding inference adds some CPU load to the API container and a
  one-time model download on first run — documented in the README's setup
  instructions so it isn't mistaken for a hang.
- Retrieval quality is good enough for the demo corpus size but is
  explicitly flagged in the README as the first thing to upgrade
  (swap to Voyage/OpenAI, or add re-ranking) if this were a real production
  system with a larger, noisier corpus.

## Links

- ADR-0002 (core tech stack)
- `ROADMAP.md` Phase 2 (ingestion pipeline)
