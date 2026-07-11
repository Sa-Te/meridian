# ADR-0014: Frontend architecture

Status: Accepted
Date: 2026-07-11

## Context

Phase 7 is the first UI-heavy phase and the first time this project's
"ports and adapters, no framework magic" posture (ADR-0002/0003) had to be
applied to a frontend rather than the FastAPI backend. It's also the phase
judged most directly on "creativity in UI/UX and product innovation," per
CLAUDE.md Section 3's glass/neumorphic design language. Four things needed
building against a bare Next.js/Tailwind skeleton: a base component
library, a chat view, a decisions/action-items view, and a traces
dashboard, plus a Playwright happy-path test tying them together.

Several concrete decisions came out of actually building this, not just
planning it — most only became visible once real components hit this
project's specific toolchain versions (Next.js 16, React 19,
`eslint-plugin-react-hooks`'s newer rules) or its specific host environment
(WSL with a symlinked `node_modules`). Each is recorded below with what
actually happened, not just the abstract reasoning.

## Decision

### Design system: hand-rolled components, no library

`Panel`, `Card`, `Button`, `Badge`, `Input` (`app/components/ui/`) are
plain Tailwind-styled components, not built on shadcn/MUI/Chakra/etc. Glass
tokens (`--surface`, `--shadow-glass`, `--accent`, ...) live as CSS custom
properties in `app/globals.css`, mapped into Tailwind v4's `@theme inline`
so they're usable as ordinary utility classes (`bg-surface`,
`shadow-[var(--shadow-glass)]`, `text-accent-strong`). Both light and dark
`prefers-color-scheme` are themed, matching the existing Phase 0 skeleton's
own dark-mode media query.

**One accent colour, with one deliberate exception.** CLAUDE.md Section 3
asks for a single restrained accent (muted teal) and near-monochrome greys
everywhere else. `Badge`'s `danger` tone is the one departure: a genuine
error state (a failed trace, a fetch error) needs to be visually
distinguishable from neutral or successful states, which pure grey can't
do. It's a desaturated, low-chroma red-brown, not a bright alert red --
still restrained, not neon, but a second colour nonetheless. Documented
here rather than silently introduced.

### Data fetching: plain client-side fetch everywhere, no Server Components split

Every view (`ChatView`, `MeetingsListView`, `MeetingDetailView`,
`TracesListView`, `TraceDetailView`) is a Client Component fetching its own
data via `useEffect` + local `useState`, the same pattern Phase 0's
`page.tsx` already established for its health check. Next.js App Router
would support a faster-perceived-load split (Server Components fetching
initial data, Client Component islands only for interactive pieces like
action-item filtering), but that means two different data-fetching
mental models in one small app for a marginal gain at this data volume and
this app's actual usage pattern (a local demo, not a
latency-sensitive production surface). One consistent, simple pattern
throughout was chosen deliberately over mixing two paradigms.

`app/lib/api/client.ts` holds hand-written TypeScript types mirroring
`app/models/schemas.py` and thin `fetch` wrappers (`askQuestion`,
`listMeetings`, `listTraces`, ...), not a generated client. At this schema
surface size, codegen tooling would be more machinery than the problem
needs; the ROADMAP's "no framework magic without justification" standard
applies as much to the frontend as the backend.

### No shared generic data-fetching hook

A first attempt shared one generic `useApiQuery(fetcher, deps)` hook
wrapping `useEffect`/`useCallback` and forwarding a caller-supplied `deps`
array. This project's `eslint-plugin-react-hooks` version hard-rejects any
non-literal-array-expression dependency list at the call site --
`Expected the dependency list for useCallback to be an array literal` --
and unlike most lint rules, this one cannot be suppressed with a disable
comment; it's a structural check the rule performs regardless. A generic
hook forwarding a dependency array can never satisfy it.

The fix: `useAsyncState<T>()` (`app/lib/api/useAsyncState.ts`) shares only
the `{data, error, loading}` state shape and `start`/`succeed`/`fail`
setters -- no `useEffect` inside it at all. Each view writes its own
`useEffect` with a genuinely literal dependency array (e.g. `[meetingId]`),
calling into the shared state actions from its own `.then()`/`.catch()`.
Slightly more code per view than a fully generic hook would need, but
every dependency array is real and independently readable -- arguably more
transparent, not just a workaround.

### `react-hooks/set-state-in-effect` is suppressed, not restructured around

Every data-fetching `useEffect` in this codebase resets `loading`/`error`
synchronously before starting its fetch -- the exact pattern React's own
documentation demonstrates for data fetching in an effect
(https://react.dev/reference/react/useEffect#fetching-data-with-effects:
`setBio(null)` called directly in the effect body, before `fetchBio(...)`).
This project's `eslint-plugin-react-hooks` version flags the *first*
synchronous `setState` call in any effect body as a potential source of
"cascading renders," with no exception for this canonical case. Each
occurrence carries a `// eslint-disable-next-line
react-hooks/set-state-in-effect` with a comment pointing back to this ADR,
rather than restructuring around a lint rule that, on inspection, is
flagging React's own documented pattern rather than a real bug in this
code.

### "Streamed answer" means a loading state, not token streaming

`POST /ask` returns one complete JSON response; there is no
partial-token/SSE endpoint to stream from. This isn't just an unbuilt
feature -- it's in real tension with ADR-0007's citation-enforcement
guardrail, which needs the *entire* response before it can even be parsed
and validated against the retrieved chunk set. Streaming raw tokens as
they arrive would mean showing prose before it's known whether the
citations in it are real, which is exactly what the guardrail exists to
prevent. `ChatView` implements the ROADMAP's "streamed answer" as a
pending -> arrived loading state instead. Building real streaming well
would mean re-architecting citation validation to work over a partial
response (or validating only after the stream completes and then revealing
the buffered result, which is just this same pending -> arrived UX with
extra steps) -- flagged here and in the README's "what I'd do differently"
as a real gap, not silently designed around.

### Backend schema changes made to support the frontend

Two small, targeted backend additions, both driven directly by a Phase 7
requirement the existing API genuinely couldn't satisfy:

- **`GET /meetings` and `GET /meetings/{id}`** (new `MeetingSummaryRead`
  schema, `MeetingRepository.list_all`). Before this phase, there was no
  way to discover which meetings exist at all -- every prior endpoint
  required already knowing a `meeting_id`. `MeetingSummaryRead` omits
  `raw_text` (irrelevant to a picker/header view, and potentially a whole
  transcript's worth of text per row).
- **`CitationRead` gained a `text` field, and `DecisionRead`/
  `ActionItemRead` replaced their flat `source_chunk_id: UUID` with a
  nested `source_citation: CitationRead`.** The ROADMAP asks citation
  chips to "reveal the source chunk (speaker, timestamp, text) inline" and
  decisions/action items to be "linked back to its source citation" --
  neither is possible from a bare chunk id. `source_citation` is built
  server-side from already-loaded chunk data (`meeting.chunks` for the
  per-meeting endpoints, an eager-loaded `ActionItem.source_chunk` for the
  global one) -- the same "never trust the client, resolve from the
  actually-retrieved record" posture ADR-0007 established for ask
  citations, now applied uniformly everywhere a citation appears. Existing
  Phase 4 tests were updated to match; see
  `apps/api/tests/integration/test_decisions_and_action_items.py`.

### No transcript-ingestion UI

The ROADMAP names exactly four frontend pieces for this phase (design
system, chat, decisions/action-items, traces) and explicitly allows
"ingest a transcript (or use seeded data)" for the Playwright test.
Building an upload screen wasn't one of the four, so it wasn't built --
ingestion remains API/seed-driven (`POST /meetings/ingest`,
`scripts/load_transcript.py`, or the Playwright test's own direct API
call). A deliberate scope boundary, not an oversight.

### Action-item owner/status filtering is client-side

`MeetingTimeline` fetches all of a meeting's action items unfiltered and
filters by owner/status in the browser, rather than adding query
parameters to `GET /meetings/{id}/action-items` (unlike the existing
global `GET /action-items?status=&owner=`, which already had them from
Phase 4). A single meeting's action-item count is small (the seed
transcripts produce single digits per meeting); filtering that in the
browser is simpler than adding, testing, and maintaining a second
filtering code path for a dataset this size.

### The decisions/action-items timeline orders by citation timestamp, not extraction time

Decisions and action items are merged into one list sorted by
`source_citation.start_ts` -- when the thing was actually said in the
meeting -- not `created_at` (when the extraction pipeline inserted the
row). Every item from one ingestion's extraction pass gets a `created_at`
within milliseconds of every other, which carries no real chronological
signal; `start_ts` is the only field that actually reflects "when in the
meeting did this happen."

### Playwright targets a running Docker Compose stack, not an auto-started dev server

`playwright.config.ts` has no `webServer` block. On this project's WSL
development host, `apps/web/node_modules` is symlinked to a directory on
the native Linux filesystem (a pre-existing performance workaround for
slow npm I/O across the Windows/WSL mount boundary) -- and Turbopack, the
default bundler for both `next dev` and `next build` in Next.js 16, panics
on that symlink ("points out of the filesystem root") regardless of
command. This is host-environment-specific, not a code issue: the same
source builds and runs cleanly inside the project's own `apps/web`
Docker image, where `node_modules` is a normal in-container directory.
Playwright is configured to hit an already-running stack
(`docker compose up`) via `PLAYWRIGHT_BASE_URL`/`PLAYWRIGHT_API_URL`
env vars (defaulting to this project's own `docker-compose.yml` ports)
instead of trying to launch Next.js itself. A CI environment without this
symlink could reasonably use Playwright's own `webServer` orchestration
directly; this project's actual dev host cannot, so this ADR documents
the workaround rather than a config CI could copy verbatim.

Running this for real also surfaced a genuine, pre-existing local
configuration bug, not a code defect: `.env`'s `WEB_PORT` had been changed
to `3001` (avoiding a conflict with an unrelated project already bound to
port 3000 on this host) without updating `CORS_ORIGINS` to match, so the
browser's cross-origin fetches from `http://localhost:3001` to the API
were silently rejected. Fixed in `.env` (gitignored, not committed code)
once discovered via the first real end-to-end run.

## Alternatives considered

- **A component library** (shadcn/ui, MUI, Chakra). Rejected: the glass/
  neumorphic language CLAUDE.md asks for is specific enough (translucent
  blur, soft dual-tone shadows, one accent) that adapting a general-purpose
  library's defaults would likely take as much effort as five small
  hand-rolled components, with an added dependency and less direct control
  over exactly this look.
- **Server Components for read-only views, Client Components only for
  interactive islands.** Rejected for this phase -- see "Data fetching"
  above. A reasonable direction if this app's data volume or perceived-
  latency requirements grow; not justified yet.
- **A generated API client** (openapi-typescript, orval, etc.) instead of
  hand-written types/fetchers. Rejected at this schema size for the same
  "no framework magic without justification" reasoning as the rest of this
  project; worth revisiting if the schema surface grows substantially.
- **Real token streaming for the chat answer**, either by streaming raw
  LLM tokens before guardrail validation or restructuring citation
  enforcement to validate incrementally. Rejected for this phase -- see
  "Streamed answer" above; a real architectural project of its own, not a
  frontend-only change.
- **Restructuring effects to avoid `react-hooks/set-state-in-effect`
  entirely** (e.g. keying components by their id to force a remount instead
  of resetting state manually). Rejected: heavier than the problem needs,
  and the pattern being flagged is React's own documented one -- see that
  section above.
- **Query-parameter filtering on `GET /meetings/{id}/action-items`**,
  mirroring the existing global endpoint. Rejected for now -- see
  "client-side" reasoning above; revisit if a meeting's action-item count
  grows enough that client-side filtering becomes wasteful.

## Consequences

- Five backend response shapes changed (`MeetingSummaryRead` added;
  `CitationRead`, `DecisionRead`, `ActionItemRead` reshaped) specifically
  to support the frontend -- a real instance of frontend requirements
  driving backend schema evolution, documented here rather than only in
  commit history.
- The chat view's "loading" state is an honest stand-in for streaming, not
  streaming itself -- flagged in the README's "what I'd do differently"
  per CLAUDE.md Section 10, alongside the real architectural work true
  streaming would need.
- `eslint-disable` comments for `react-hooks/set-state-in-effect` appear in
  every data-fetching view (four call sites) -- a deliberate, documented
  exception, not scattered unexplained suppressions; a reviewer hitting
  one can trace it back to this ADR.
- No ingestion UI exists yet; a real user of this system has to use the
  API directly or `scripts/load_transcript.py` to add a meeting. Named
  directly as an explicit Phase 7 scope boundary, not a silent gap.
- Playwright's happy-path test requires a running `docker compose up`
  stack (or an equivalent `PLAYWRIGHT_BASE_URL`/`PLAYWRIGHT_API_URL`
  target) rather than being fully self-starting -- a real constraint of
  this project's dev host, worth revisiting if CI wiring (a natural
  Phase 9 candidate) needs it to be self-contained instead.

## Links

- ADR-0002/0003 (core tech stack, custom orchestration vs. framework) --
  the "no framework magic without justification" standard applied here to
  the frontend's component library and API client choices
- ADR-0007 (retrieval and citation strategy) -- the citation-enforcement
  guardrail behind the "streamed answer" decision, and the "resolve
  citations server-side" posture this phase extends to decisions/action
  items
- ADR-0010 (observability approach) -- the `GET /traces`/`GET
  /traces/{id}` surface the traces dashboard renders
- CLAUDE.md Section 3 (design language) -- the glass/neumorphic
  requirements this phase implements
- `ROADMAP.md` Phase 7 (frontend: chat, decisions/action-items, and traces
  dashboard)
- `apps/web/app/components/`, `apps/web/app/lib/api/`,
  `apps/web/e2e/happy-path.spec.ts`, `apps/web/playwright.config.ts`
- `apps/api/app/models/schemas.py` (`MeetingSummaryRead`, `CitationRead`,
  `DecisionRead`, `ActionItemRead`), `apps/api/app/services/citations.py`
