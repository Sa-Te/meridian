# Architecture decision records — index

Every non-trivial decision in this project gets an ADR, written before or
immediately after the code that implements it (`CLAUDE.md` Section 6).
`0000-template.md` is the blank template new ADRs are written from, not a
decision itself. Numbering is sequential and never reused; `0012` is not
a gap — it's reserved for, and used by, the voice-to-transcript phase,
which landed after the phases numbered above it in the ROADMAP but was
drafted early in the sequence.

| ADR | Title |
|-----|-------|
| [0001](0001-assignment-option-and-product-framing.md) | Assignment option and product framing |
| [0002](0002-core-tech-stack.md) | Core tech stack |
| [0003](0003-custom-orchestration-vs-framework.md) | Custom orchestration instead of a RAG framework |
| [0004](0004-vector-storage-and-embedding-provider.md) | Vector storage and embedding provider |
| [0005](0005-domain-schema.md) | Domain schema for Meeting, Chunk, Decision, and ActionItem |
| [0006](0006-chunking-strategy.md) | Speaker-turn-aware chunking strategy |
| [0007](0007-retrieval-and-citation-strategy.md) | Retrieval and citation strategy |
| [0008](0008-structured-extraction-and-guardrails.md) | Structured extraction and guardrails |
| [0009](0009-evaluation-methodology.md) | Evaluation methodology |
| [0010](0010-observability-approach.md) | Observability approach |
| [0011](0011-mcp-exposure.md) | Expose the backend as an MCP server, not just a REST API |
| [0012](0012-voice-to-transcript-and-diarization.md) | Voice-to-transcript ingestion with real speaker diarization |
| [0013](0013-switch-default-llm-to-gemini.md) | Switch the default LLM provider from Anthropic to Gemini |
| [0014](0014-frontend-architecture.md) | Frontend architecture |
| [0015](0015-ci-coverage-and-pipeline-ordering.md) | Coverage tooling, the greenlet coverage blind spot, and fail-fast CI ordering |
| [0016](0016-eval-suite-ci-gating-and-quota-conservation.md) | Move the eval-suite gate off the per-push CI pipeline |

## Reading order for a reviewer short on time

If you're not reading all sixteen: **0001** (why this product), **0004**
and **0007** (the two decisions the assignment most directly asks to see
justified — vector storage/embeddings and retrieval strategy), **0009**
(how quality is actually measured, with real numbers), and **0012** (the
most recently built, and the one with the most real engineering friction
documented end to end). The root `README.md`'s
[Key technical decisions](../../README.md#5-key-technical-decisions-and-why)
section has a one-line summary of every ADR in the table above if you
want the condensed version first.

## Supersession chain

A few ADRs amend earlier ones rather than standing alone — read the
amended one first, then the amendment, not the other way around:

- **0013** supersedes the LLM-provider-choice paragraph of **0002** only;
  everything else in 0002 still stands.
- **0016** supersedes the eval-suite-gate-placement portion of **0015**;
  everything else in 0015 (coverage tooling, the greenlet fix, fail-fast
  ordering within a push) still stands.
