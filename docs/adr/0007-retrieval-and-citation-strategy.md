# ADR-0007: Retrieval and citation strategy

Status: Accepted
Date: 2026-07-11

## Context

Phase 3 is the core "answer questions using RAG" requirement from the
assignment. Given a question, the system needs to (1) find the chunks most
likely to answer it, and (2) generate an answer that is verifiably grounded
in those chunks, not a fabrication. Both halves needed a concrete, testable
design: the assignment explicitly asks for pgvector cosine similarity
combined with Postgres full-text search, fused with a simple weighted
score rather than a full cross-encoder re-ranker, and asks for the
citation-enforcement approach to be documented.

## Decision

### Hybrid retrieval

- **Vector side:** cosine similarity over `Chunk.embedding` via pgvector's
  `<=>` operator (exposed through `pgvector.sqlalchemy`'s
  `Vector.cosine_distance()`), converted to a similarity score
  (`1 - distance`) so higher is better, consistent with the text-search
  side.
- **Text side:** Postgres full-text search via a new `search_vector`
  column on `chunks` -- a `tsvector` **generated column**
  (`GENERATED ALWAYS AS (to_tsvector('english', text)) STORED`) with a GIN
  index, added in migration `dd7bdb752c64`. A generated column keeps
  `search_vector` in sync with `text` automatically; there is no
  application code path that can write `text` and forget to update the
  search index, unlike a trigger or a manually-maintained column. Queries
  use `plainto_tsquery('english', question)` against `search_vector`,
  ranked by `ts_rank`.
- **No ANN index on `embedding` yet.** `Chunk.embedding` remains an
  unindexed (flat/exact) vector column. Same reasoning as ADR-0004: the
  corpus here is a handful of synthetic transcripts, not the "few million
  chunks" scale where an ivfflat/hnsw index's build cost and recall
  trade-off start to pay for themselves. Revisit alongside ADR-0004's
  documented trigger.
- **Fusion:** each side's raw scores are independently min-max normalized
  to `[0, 1]` across the current candidate set, then combined as
  `vector_weight * normalized_vector + text_weight * normalized_text`.
  Normalization is necessary because cosine similarity and `ts_rank` live
  on unrelated, non-comparable scales -- summing them raw would let
  whichever signal happens to produce larger numbers dominate regardless
  of actual relevance. A chunk found by only one method contributes 0 for
  the side it's missing rather than being excluded from the ranking
  entirely, so a chunk with a strong full-text match but no vector-search
  presence (or vice versa) can still surface.
- **Weights and pool size:** `vector_weight=0.6`, `text_weight=0.4`,
  `candidate_pool_size=25` (candidates fetched from *each* method before
  fusion), `top_k=8` (chunks passed to generation), all configurable via
  `Settings`/environment variables. Vector search is weighted slightly
  higher because it is the signal expected to generalize better to
  paraphrased questions that don't share literal vocabulary with the
  transcript; full-text search is weighted meaningfully anyway because
  exact-term questions (names, numbers, specific phrases -- common in a
  meeting-notes QA setting) are exactly where lexical search reliably
  outperforms embedding similarity. `top_k=8` is a starting point sized to
  the demo corpus (transcripts chunked into dozens of chunks each, not
  thousands); Phase 5's eval harness, scoring retrieval recall@k against a
  golden dataset, is the intended mechanism for tuning all four of these
  numbers with real evidence instead of intuition.
- **Not a cross-encoder re-ranker.** A cross-encoder (or any model that
  jointly scores question+chunk pairs) would likely out-rank this simple
  weighted fusion, especially for paraphrased or multi-hop questions. It
  was deliberately not built for this phase: it adds a second model
  (another local inference cost or another API dependency), and the
  assignment explicitly calls out noting this exact trade-off rather than
  building it. If eval numbers from Phase 5 show fusion ranking is the
  retrieval quality bottleneck, a re-ranking pass over the fused top-N is
  the natural next step, sitting cleanly between `hybrid_search` and
  `generate_answer` without touching either.

### Chunk search lives in its own repository

`ChunkRepository` (`app/repositories/chunk_repository.py`) is new, separate
from `MeetingRepository`. CLAUDE.md's "one repository per aggregate root"
rule is about write/consistency boundaries -- `Decision` and `ActionItem`
never get their own repository because they're never persisted or loaded
independently of their owning `Meeting`. Retrieval is different: it's a
read-only query that the global `POST /ask` endpoint runs *across*
meetings, which doesn't fit inside a single aggregate's repository at all.
Rather than bolt a cross-aggregate query onto `MeetingRepository`, it gets
its own repository scoped to the query capability (`vector_candidates`,
`text_candidates`), keeping `MeetingRepository` focused on `Meeting`
aggregate persistence.

### Citation enforcement

The LLM (`LLMProvider.generate`, Gemini by default per ADR-0013) is asked
to return a single JSON object: `{"supported": bool, "answer": str,
"citations": [{"chunk_id": str}, ...]}`. This is plain prompted JSON, not
vendor tool-calling/structured output -- keeping generation on the same
`LLMProvider.generate(messages, system) -> LLMResponse` interface used
everywhere else, so nothing here is tied to a Gemini-specific capability.
Tool-calling is reserved for Phase 4's structured extraction, where the
shape being extracted (decisions, action items) is a better fit for it.

The response is guardrail-checked before being trusted:

1. It must parse as JSON matching the expected schema (a `pydantic` model
   validates it).
2. If `supported` is `true`, `citations` must be non-empty, and every
   `chunk_id` must be one of the chunk ids that were actually retrieved
   for this question. A citation to any other id -- a hallucinated id, or
   a real chunk id from outside the retrieved set -- fails validation.
3. If `supported` is `false`, the model's own answer and empty citation
   list are accepted as-is: an honest "I don't know" is not a guardrail
   failure, it's the correct outcome for an out-of-scope question.

A guardrail failure (malformed JSON, or an invalid/missing citation) is
not surfaced to the user directly. The request is retried exactly once,
with a stricter instruction appended to the system prompt reiterating the
schema and warning that the previous attempt was rejected. If the retry
also fails, the endpoint returns a fixed, honest response ("I could not
find a well-supported answer to this question in the available
transcripts") rather than either an error or a fabricated answer.
`start_ts`/`end_ts`/`speaker`/`meeting_id` in the final `CitationRead` are
looked up server-side from the actually-retrieved `Chunk` rows, not taken
from the model's response -- the model only ever needs to get a
`chunk_id` right, which is the one fact that's actually checkable.

This citation-check logic lives in its own module
(`app/services/answer_generation.py`) precisely so Phase 4's guardrails
module can reuse it rather than duplicate or rewrite it, per
CLAUDE.md's DRY principle and the ROADMAP's own note that Phase 3's
citation enforcement is a preview of Phase 4's fuller guardrails.

### Endpoints

Both `POST /meetings/{meeting_id}/ask` (retrieval scoped to one meeting)
and `POST /ask` (retrieval across all meetings) are implemented, sharing
one internal `_ask` helper in `app/routers/ask.py`. `meeting_id` not found
returns 404 before any retrieval work happens.

## Alternatives considered

- **Cross-encoder re-ranking pass over the fused candidates.** Rejected
  for this phase -- see "Not a cross-encoder re-ranker" above. The
  trade-off is explicit rather than silently absent.
- **Reciprocal Rank Fusion (RRF)** instead of weighted-sum-of-normalized-
  scores. RRF (summing `1 / (k + rank)` across each ranking) avoids
  needing to normalize raw scores at all and is a common, robust default.
  Weighted-sum was chosen instead because the assignment explicitly asked
  for "a simple weighted score," and because min-max normalization plus an
  explicit weight is more directly explainable and tunable (a single
  `vector_weight`/`text_weight` knob) than RRF's rank-based `k` constant,
  which is a reasonable trade for a system this size where explainability
  in an interview matters as much as ranking robustness.
- **Vendor tool-calling / structured output for the citation JSON**
  (e.g. Gemini's response schema mode) instead of a plain-text prompt
  parsed with `pydantic`. Rejected for this phase to keep generation
  fully vendor-agnostic through the existing `LLMProvider.generate`
  interface; reconsidered if Phase 4's extraction work needs it, where the
  more complex Decision/ActionItem shape is a better argument for it.
- **A confidence-threshold cutoff on the fused score**, skipping
  generation entirely below some threshold. Deliberately deferred to
  Phase 4, which names this exact idea ("a confidence threshold below
  which the system declines to answer rather than guessing") as its own
  guardrail. Phase 3 relies solely on the LLM's own `supported` judgment,
  which the integration tests confirm is sufficient to avoid fabrication
  for an out-of-scope question even before a numeric cutoff exists.
- **A trigger-maintained `search_vector` column** instead of a generated
  column. Rejected: Postgres 12+ generated columns do the same job with
  less code (no trigger function to write, test, and keep in sync with
  the `chunks` schema) and are the more idiomatic choice for a
  derived-and-always-in-sync column.

## Consequences

- Retrieval quality depends on two independently-tunable weights and a
  fixed `top_k`, all currently chosen by reasoning rather than measurement
  -- Phase 5's eval harness is the concrete plan for replacing that
  reasoning with data.
- The lack of a cross-encoder re-ranker means retrieval quality on
  paraphrased or multi-hop questions is weaker than a production system
  would likely want; documented here and in the README as a known
  limitation rather than something silently missing.
- Citation enforcement adds up to one extra LLM call (the retry) on a
  guardrail failure, a latency/cost trade-off accepted in exchange for
  materially reducing fabricated-citation risk.
- `ChunkRepository` is a second repository whose existence is justified
  by a read/write distinction that isn't spelled out in CLAUDE.md itself
  -- this ADR is that justification, and the next repository added to this
  codebase should follow the same reasoning (is it aggregate persistence,
  or cross-aggregate query?) rather than defaulting to "one repository per
  table."

## Links

- ADR-0004 (vector storage and embedding provider)
- ADR-0005 (domain schema) -- `Chunk.embedding` and citation-first framing
- ADR-0006 (chunking strategy) -- notes Phase 3 as the first real signal
  on chunk sizing
- ADR-0013 (switch default LLM to Gemini)
- `ROADMAP.md` Phase 3 (retrieval and RAG question-answering) and Phase 4
  (structured extraction and guardrails)
- `app/services/retrieval.py`, `app/services/answer_generation.py`,
  `app/repositories/chunk_repository.py`, `app/routers/ask.py`
- Migration `dd7bdb752c64` (add chunk full-text search vector)
