# ADR-0011: Expose the backend as an MCP server, not just a REST API

Status: Accepted
Date: 2026-07-12

## Context

The Newpage FDE job description explicitly lists "experience building
applications involving MCPs" as a desired qualification. Meridian's core
value -- searching, asking questions about, and pulling structured facts
out of past client meetings -- is already fully implemented behind a REST
API (`POST /ask`, `GET /search`, `GET /action-items`). The question this
ADR answers is not "how do we build this capability" (already built) but
"what does exposing it over MCP add that the REST API alone doesn't."

An FDE's actual day-to-day workflow is inside an AI coding assistant
(Claude Code, Claude Desktop) -- writing code, debugging, prepping for a
client call. The realistic value case for this phase is that same FDE
asking their assistant "what did we decide about alert thresholds in the
clinical advisory meeting?" or "what's still open for Dr. Vasquez?"
without leaving that assistant, opening a browser, or writing a `curl`
command. MCP is the standard way to give an assistant that capability
without teaching it a bespoke API contract per project.

## Decision

Build a small MCP server, `apps/mcp_server/`, as its own Python package --
a peer client of the FastAPI backend (ROADMAP.md Phase 11's architecture
diagram), not a module inside `apps/api`. It uses the official MCP Python
SDK (`mcp`, pinned `>=1.28,<2` -- the stable v1.x line; v2 is
pre-release/alpha as of this writing, see the SDK's own README) via its
high-level `FastMCP` API, and exposes three tools:

- `search_meetings(query, top_k=8)` -- raw ranked chunk retrieval, no
  generation. Calls the new `GET /search` endpoint (added in this phase;
  hybrid_search's retrieval logic already existed for the ask flow, but
  had no standalone REST surface to call).
- `ask_meetings(question, meeting_id=None)` -- a cited, generated answer.
  Calls `POST /ask` or `POST /meetings/{id}/ask`.
- `get_action_items(status=None, owner=None)` -- structured action-item
  lookup. Calls `GET /action-items`.

**The MCP server contains zero retrieval, generation, or extraction
logic.** `mcp_server/client.py` is a thin `httpx.AsyncClient` wrapper with
one method per backend call; `mcp_server/server.py`'s three `@mcp.tool()`
functions do nothing but call it and reshape the JSON response into the
tool's return value. Every guardrail, ranking decision, and confidence
threshold lives exactly once, in `apps/api`, exercised identically whether
the caller is the web frontend, a `curl` command, or an MCP host. This is
the same ports-and-adapters instinct as ADR-0002/0003's `LLMProvider`
abstraction, applied to the boundary between "who's asking" and "the one
place that answers" rather than between "which vendor" and "the one
interface."

**Transport is stdio, not Streamable HTTP.** Claude Desktop and Claude
Code both spawn a locally configured MCP server as a subprocess and speak
stdio to it -- this is the standard, zero-infrastructure integration point
for exactly the workflow this ADR is justifying (a developer's own
assistant, on their own machine, during their own work). Streamable HTTP
matters for a server that itself needs to be a persistent, independently
deployed, multi-client network service; nothing about this project's
scope needs that yet, and choosing it now would mean standing up and
authenticating a network-facing process for a capability that a stdio
subprocess already serves fully.

**Why `GET /search` needed to be added, not just called.** `hybrid_search`
(the retrieval half of the ask flow, ADR-0007) already existed as a
service function, but was only reachable through `POST /ask`'s
generate-an-answer flow -- there was no way to get back ranked chunks
without also paying for an LLM call. Adding the endpoint is a thin router
(`app/routers/search.py`) that composes existing pieces
(`ChunkRepository`, `hybrid_search`, `build_citation`) exactly the way
`app/routers/ask.py` already does; no retrieval logic changed. It is
deliberately **not** wrapped in `TraceRecorder` the way the ask and ingest
flows are (ADR-0010): that ADR scopes tracing specifically to the two
LLM/embedding-cost flows worth measuring, and `TraceOutcome`'s vocabulary
(`answered`/`declined`/`error`) is ask-flow-shaped in a way that doesn't
fit a pure-retrieval endpoint. Extending tracing to cover this would be a
real scope change to ADR-0010, not a natural fit for this phase.

## Alternatives considered

- **Have the MCP tools import `apps/api`'s service modules directly**
  (call `hybrid_search`, `generate_answer`, etc. in-process instead of over
  HTTP). Rejected: this is exactly the "second implementation" the
  ROADMAP's own prompt warns against. It would need its own DB session,
  its own provider instantiation, and would silently drift from whatever
  guardrail/confidence logic the API's routers apply -- two places that
  can each remember (or forget) a fix.
- **Expose retrieval only through a resource, not a tool.** MCP resources
  are meant for read-only context the host loads passively; `search`,
  `ask`, and `get_action_items` are each parameterized queries a host
  decides to invoke conditionally mid-conversation, which is exactly what
  MCP tools model. Nothing here is a fixed, non-parameterized document to
  expose as a resource.
- **A fourth tool for ingestion** (`ingest_meeting`). Left out: ingestion
  is a write with real side effects (persists a meeting, calls the LLM for
  extraction, costs real tokens) that an AI assistant should not be able
  to trigger implicitly from a conversational prompt without the human
  reviewing what's about to be ingested. Search/ask/action-items are all
  read-only queries; that boundary is deliberate, not an oversight.

## Consequences

- **What this makes possible**: an FDE (or a reviewer of this take-home)
  can point Claude Desktop or Claude Code at a running Meridian backend
  and ask it about past meetings directly, with zero custom glue code on
  the assistant side -- exactly the JD line this phase is answering.
- **What this makes harder**: nothing structurally; the MCP server adds a
  new process to run locally, documented in the README setup section, but
  changes no existing code path's behavior.
- **Explicit out of scope: no MCP-side authentication or authorization.**
  The stdio transport runs as a local subprocess under the same user who
  configured it, with no separate identity or credential of its own -- it
  inherits whatever access the running backend allows, which today (see
  CLAUDE.md Section 9's non-goals) is a single-user, unauthenticated local
  system. A production deployment exposing this over a network transport
  (Streamable HTTP, per the SDK's own `docs/authorization.md`) would need
  OAuth 2.1 token verification at the MCP layer, scoped credentials
  per FDE/user, and audit logging of which tool calls touched which
  client's data -- none of which exists here, and none of which this
  submission's single-user scope requires yet.
- **What would trigger revisiting this**: a second MCP host needing a
  different transport (Streamable HTTP for a hosted, multi-user
  deployment), or a real need for the MCP server to trigger writes
  (ingestion) rather than only reads.

## Links

- ADR-0002/0003 (core tech stack, ports and adapters) -- the same
  boundary-abstraction reasoning applied here to "caller" rather than
  "vendor"
- ADR-0007 (retrieval and citation strategy) -- `hybrid_search`, reused
  as-is by the new `GET /search` endpoint
- ADR-0010 (observability approach) -- why `GET /search` is deliberately
  not traced
- `ROADMAP.md` Phase 8 (MCP server exposure), Phase 11 (README
  architecture diagram showing the MCP server as a peer client of the API)
- `apps/mcp_server/` (`server.py`, `client.py`, `config.py`), `apps/api/app/routers/search.py`
