# ADR-0005: Domain schema for Meeting, Chunk, Decision, and ActionItem

Status: Accepted
Date: 2026-07-10

## Context

Phase 1 needs a settled relational + vector schema before ingestion (Phase
2), retrieval (Phase 3), and structured extraction (Phase 4) can be built
against it. ADR-0001 committed this project to more than plain document
Q&A: decisions and action items are first-class entities, each citing the
specific transcript segment they were drawn from, not just a flat chunk
store. ADR-0004 already committed to Postgres + pgvector as the single
storage engine, so this ADR is scoped to shape, not engine choice.

Several modelling choices here aren't obvious from the ROADMAP.md field
list alone and are recorded below, along with a real bug the test suite
caught while building this schema.

## Decision

Four tables: `meetings`, `chunks`, `decisions`, `action_items`, defined as
SQLAlchemy 2.0 ORM models in `apps/api/app/models/orm.py`, migrated via Alembic
(`apps/api/alembic/versions/`), with corresponding Pydantic schemas in
`apps/api/app/models/schemas.py` used for every API request/response shape so ORM
objects never cross the API boundary directly.

The non-obvious choices:

- **UUID primary keys, generated client-side** (`default=uuid.uuid4`), not
  auto-incrementing integers. Meeting/chunk/decision ids are referenced in
  citations surfaced to users (Phase 3) and potentially in URLs; UUIDs avoid
  leaking a sequential count of how many meetings or chunks exist, and
  client-side generation means an id is available immediately after
  constructing an object, before any DB round trip.
- **`confidence` is stored per-row on `Decision` and `ActionItem`**, not on
  `Meeting`, and it's a required `Float` with a DB-level
  `CHECK (confidence >= 0 AND confidence <= 1)`, not just a Pydantic-layer
  validation. Confidence is a property of a single extracted claim, not of
  the meeting it came from -- two decisions extracted from the same meeting
  can have meaningfully different extraction certainty (an explicit "we
  decided X" versus an inferred one), and Phase 4's guardrail work
  (declining to answer, or flagging low-confidence items) needs to filter
  and threshold on it per-row. Enforcing the range at the DB layer, not just
  in the Pydantic `Create` schemas, means no code path -- including a future
  script or a direct DB write -- can silently insert a nonsense confidence
  value.
- **`source_chunk_id` is required (`NOT NULL`), not optional, on both
  `Decision` and `ActionItem`.** An extracted decision or action item with
  no citation back to the transcript segment it came from is exactly the
  failure mode ADR-0001's citation-first framing exists to prevent -- an
  unfalsifiable claim. Making it a required FK rather than a nullable one
  means the database itself refuses to represent that state, instead of
  relying on every future write path (extraction in Phase 4, any manual
  correction tooling later) to remember to attach one.
- **`source_chunk_id` cascades on delete (`ON DELETE CASCADE`), not
  `RESTRICT`.** The first version of this schema used `RESTRICT`, on the
  reasoning that deleting a chunk out from under a decision that cites it
  sounded like something that should be blocked. In practice this created a
  real bug: `meetings.id` also cascades to `chunks` and to `decisions`/
  `action_items` independently, and Postgres does not guarantee those two
  cascade paths fire in an order where the citing rows are always gone
  before the cited chunk is deleted -- deleting a `Meeting` could then fail
  with a `RESTRICT` violation depending on trigger firing order. Changing
  `source_chunk_id` to `ON DELETE CASCADE` makes "delete a chunk" and
  "delete a chunk's meeting" both correctly remove any decision/action item
  that cited it, order-independent, and keeps the invariant above intact:
  a `Decision`/`ActionItem` can never outlive its citation. This also
  surfaced a second, related bug during testing: SQLAlchemy's ORM does not
  trust the DB's `ON DELETE CASCADE` by default -- on deleting a `Chunk` it
  tried to `UPDATE ... SET source_chunk_id = NULL` on the citing rows
  first, which then failed the `NOT NULL` constraint. The fix was adding
  `passive_deletes=True` to `Chunk.decisions` / `Chunk.action_items`, which
  tells SQLAlchemy to let Postgres's cascade handle child rows instead of
  managing it in Python. Both integration tests
  (`apps/api/tests/integration/test_domain_schema_constraints.py`) exercise this
  directly -- deleting a meeting, and separately deleting a chunk, and
  asserting the citing rows are actually gone.
- **`start_ts`/`end_ts` on `Chunk` are integer seconds elapsed from the
  start of the meeting**, not wall-clock timestamps and not a Postgres
  `INTERVAL`/`TIME` column. The transcripts encode elapsed-time markers
  (`[00:03:12]`), not calendar time, so a wall-clock type would imply
  precision that doesn't exist. Plain integers are trivial to compare, sort,
  and do arithmetic on, and sidestep timezone questions entirely.
- **`participants` on `Meeting` is a plain Postgres string array**, not a
  normalized `Participant` entity with a join table. Nothing in scope
  through Phase 9 needs to query "every meeting a given person attended" as
  a first-class feature -- if that need shows up later, that's the concrete
  trigger to normalize it, not before.
- **`ActionItemStatus` is a native Postgres enum** (`open`, `in_progress`,
  `done`), not a free-text column with an application-level check. A fixed,
  small status vocabulary is exactly what a DB enum is for, and it makes an
  invalid status a schema-level impossibility rather than a validation rule
  that could be bypassed.
- **`Chunk.embedding` is a nullable pgvector `Vector(768)` column**, sized
  for `BAAI/bge-base-en-v1.5`'s output dimensionality per ADR-0004, present
  in the schema now but populated starting in Phase 2. Adding the column
  now (rather than migrating it in later) means Phase 2 is a pure data-fill
  change, not a schema change.
- **`(meeting_id, chunk_index)` is unique** on `Chunk`, enforced at the DB
  level, so two chunks can never silently claim the same position within a
  meeting's ordering.

## Alternatives considered

- **A many-to-many join table letting a Decision/ActionItem cite multiple
  source chunks.** More accurate for a decision that emerges gradually
  across several turns, but real added complexity (a junction table, and
  Phase 4's extraction logic would need to choose which chunks to link) for
  a benefit this dataset's meeting lengths don't clearly need yet. Rejected
  for now; a single primary grounding chunk is required, and Phase 4's
  extraction step picks whichever chunk most explicitly states the
  decision. If false negatives from single-chunk grounding turn out to be a
  real problem once extraction is built, that's the trigger to revisit this.
- **Auto-incrementing integer primary keys.** Simpler and marginally faster
  to index, but leaks sequential counts through anything that echoes an id
  back to a client, and doesn't naturally support client-side id generation
  before a row is persisted. UUIDs were chosen instead; see Decision above.
- **Storing confidence only in the Pydantic `Create` schemas (`ge=0, le=1`),
  without a DB-level check constraint.** Rejected — a Pydantic constraint
  only protects writes that go through that specific schema. A DB check
  constraint protects every write path, present and future.

## Consequences

- The `passive_deletes=True` relationship configuration must be kept in
  mind for any future relationship added between an entity and something it
  cascades to delete via FK — the default SQLAlchemy behavior (nulling the
  FK) will silently violate a `NOT NULL` constraint otherwise, as it did
  here.
- Single-chunk citation is a real, accepted limitation for decisions/action
  items that are stated gradually across multiple turns rather than in one
  clear utterance; Phase 4's extraction quality is bounded by this until/
  unless the schema is revisited.
- `participants` as a plain array means no query today can efficiently find
  "all meetings a given person was in" without scanning; acceptable at this
  corpus size, explicitly not production-scale design.

## Links

- ADR-0001 (product framing -- decisions/action items as first-class,
  citation-first entities)
- ADR-0004 (pgvector, embedding dimensionality)
- `apps/api/app/models/orm.py`, `apps/api/app/models/schemas.py`
- `apps/api/alembic/versions/` (initial migration)
- `apps/api/tests/integration/test_domain_schema_constraints.py`
- `ROADMAP.md` Phase 2 (embeddings populate `Chunk.embedding`), Phase 4
  (extraction populates `Decision`/`ActionItem`)
