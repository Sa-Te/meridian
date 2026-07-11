# ADR-0006: Speaker-turn-aware chunking strategy

Status: Accepted
Date: 2026-07-11

## Context

Phase 2 needs to turn parsed speaker turns (`app/services/transcript_parser.py`)
into the `Chunk` rows defined in ADR-0005 -- the units retrieval (Phase 3)
searches over and cites back to the user. The assignment explicitly asks
for the chunking strategy and its trade-offs to be documented.

The obvious alternative -- fixed-size chunking (e.g. every N characters or
tokens, regardless of turn boundaries) -- is simpler to implement and is
what most naive document-Q&A pipelines default to. It was rejected: meeting
transcripts are conversational, and a fixed-size window will routinely cut
a sentence, or an entire speaker's point, in half across two chunks. A
retrieved chunk that starts mid-sentence with no speaker attribution is a
worse citation than one that starts and ends on a real conversational
boundary, which matters directly for ADR-0001's citation-first framing.

## Decision

Chunking is speaker-turn-aware (`app/services/chunking.py`):

- Consecutive turns from the **same speaker** are merged into a single
  chunk, up to a configurable token budget (`DEFAULT_MAX_CHUNK_TOKENS =
  220`). A chunk never contains more than one speaker.
- A turn never splits across a chunk boundary unless the turn **alone**
  exceeds the token budget, in which case it's split along sentence
  boundaries (never mid-sentence), each piece as large as fits.
- "Token" here means a whitespace-delimited word count, not a real
  subword/BPE token count -- see the trade-off below.

This composes with the parser as two independently testable stages, per
ADR-0003: `parse_transcript` produces `SpeakerTurn`s with real start/end
timestamps; `chunk_turns` only knows about turns and a token budget, not
about parsing or persistence.

## Alternatives considered

- **Fixed-size chunking (e.g. every 200 tokens, sliding window).** Simpler
  to implement and reason about, and it's what most naive RAG tutorials
  default to. Rejected as the primary strategy: it breaks conversational
  context by design, routinely splitting a turn (or a sentence) across two
  chunks with no regard for who said what. The cost of the more complex
  approach actually taken is real -- more code, more edge cases (see below)
  -- but it directly serves the "cite what was actually said" requirement
  that fixed-size chunking works against.
- **One chunk per turn, never merging (Phase 1's placeholder behavior).**
  Simpler than the same-speaker-merge rule below, but produces a lot of
  low-information chunks from this dataset's many short turns ("Agreed."
  "That's fair." "Confirmed."). Those are bad retrieval units on their own
  -- little semantic content, and the useful context is the fuller point a
  speaker was making across several short turns. Merging consecutive
  same-speaker turns (not merging across a speaker change) captures that
  benefit without giving up per-chunk speaker attribution.
- **Merging across a speaker change too (a pure token-budget packer,
  speaker-agnostic).** Would pack chunks more tightly and arguably improve
  retrieval density further, but conflicts with ADR-0005's `Chunk.speaker`
  column being a single value, not a list. Making a chunk hold multiple
  speakers would have required either a schema change (a list/array
  column, or a join table) this soon after ADR-0005 shipped, or picking an
  arbitrary "primary" speaker for a multi-speaker chunk, which is worse
  than just not merging across speakers. Rejected in favor of keeping
  `Chunk.speaker` an honest, single value.
- **Counting real subword tokens (the actual embedding model's tokenizer)
  instead of whitespace-delimited words.** More accurate against the local
  BGE model's real 512-token limit, but it would couple the chunking stage
  to a specific embedding model's tokenizer, which conflicts with keeping
  chunking and embedding independently testable/swappable (ADR-0003,
  ADR-0004's `EmbeddingProvider` swap). A whitespace word count is a cheap,
  dependency-free, model-agnostic proxy; the default budget (220 words) is
  set conservatively below BGE's real token limit specifically to leave
  margin for the word-to-subword-token expansion ratio in normal English
  prose. This is an approximation, accepted explicitly, not an oversight --
  if it proves too imprecise in practice (e.g. chunks silently truncated by
  the embedding model), the fix is swapping in a real tokenizer-based
  counter via the same `count_tokens` parameter `chunk_turns` already
  accepts, not a redesign.

## Consequences

- Sentence splitting is a naive regex (`.`/`!`/`?` followed by whitespace),
  which misreads abbreviations like "Dr." as a sentence end. Accepted: the
  only consequence is an extra, still-correct chunk boundary in a rare
  case, never corrupted or dropped text -- and matches CLAUDE.md's
  non-goal of not gold-plating parsing/text-processing logic.
- Sub-chunks produced by splitting one oversized turn all share that turn's
  single start_ts/end_ts pair, since the transcript format carries no
  finer-grained timing within a turn. A citation to one of these sub-chunks
  will point at the whole turn's time range, not the specific sentence.
- If a single sentence alone exceeds the token budget, it's kept whole
  rather than cut mid-sentence -- the sentence boundary is a hard floor on
  how finely this splits, by design.
- The 220-word default budget is a starting point, not a tuned value;
  Phase 3's retrieval quality work (and Phase 5's eval harness) is the
  first real signal on whether it needs adjusting.

## Links

- ADR-0001 (citation-first product framing)
- ADR-0003 (independently testable pipeline stages)
- ADR-0004 (local BGE embedding model, 512-token limit)
- ADR-0005 (`Chunk.speaker` as a single value, not a list)
- `apps/api/app/services/transcript_parser.py`, `apps/api/app/services/chunking.py`
