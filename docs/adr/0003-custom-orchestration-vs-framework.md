# ADR-0003: Custom orchestration instead of a RAG framework

Status: Accepted
Date: 2026-07-10

## Context

The assignment explicitly asks for the "orchestration framework" decision
and reasoning to be documented. Frameworks such as LangChain or LlamaIndex
would reduce the amount of pipeline code written by hand, at the cost of
introducing abstraction layers that are harder to instrument for custom
observability and harder to explain step-by-step under interview
questioning.

## Decision

Build a thin, hand-written orchestration layer for ingestion, retrieval,
and generation. No LangChain, no LlamaIndex, no agent framework for the
core pipeline. Each stage (chunk, embed, store, retrieve, rank, prompt,
generate, extract, guard) is its own small, independently testable
function or class behind the provider interfaces defined in ADR-0002.

## Alternatives considered

- **LangChain.** Would speed up initial wiring, but its retriever/chain
  abstractions make it harder to attach the custom per-stage tracing this
  project wants for the observability requirement, and it adds a large
  dependency surface for what is, at this scale, a straightforward
  pipeline. Also a weaker interview answer: "the framework handled it" is
  less convincing than being able to walk through the actual retrieval
  code.
- **LlamaIndex.** Similar reasoning — strong for rapid prototyping of
  document Q&A, but this project's structured extraction and dual-store
  (relational + vector, same instance) design doesn't map cleanly onto its
  default abstractions without fighting them.
- **A DIY orchestration framework/abstraction of its own** (i.e.
  over-building a mini-framework). Rejected — the assignment rewards a
  solid basic solution, not speculative generality. Interfaces exist only
  where a real swap (LLM/embedding/vector store vendor) is plausible.

## Consequences

- More code to write and test by hand than a framework-based approach.
- Full transparency: every prompt, every retrieval call, every extraction
  step is inspectable and traceable without framework instrumentation
  workarounds.
- If the system's scope grew to genuine multi-agent workflows, this
  decision would be revisited — noted explicitly as a "with more time"
  item in the final README rather than something silently deferred.

## Links

- ADR-0002 (core tech stack)
- `ROADMAP.md` Phase 2-3 (ingestion, retrieval)
