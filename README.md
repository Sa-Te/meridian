# Meridian

Meridian is a meeting intelligence system that ingests speaker-labelled,
timestamped meeting transcripts from a simulated health-tech consulting
engagement and answers questions about discussions, decisions, and action
items using retrieval-augmented generation.

More documentation coming. See `CLAUDE.md` for the engineering contract and
`ROADMAP.md` for the phased build plan; architecture and decision records
live under `docs/adr/`.

## MCP server

`apps/mcp_server/` exposes the backend as three MCP tools --
`search_meetings`, `ask_meetings`, `get_action_items` -- so an MCP host
(Claude Code, Claude Desktop) can query past meeting transcripts directly,
without a browser or a hand-written `curl` command. It is a thin HTTP
client of the same FastAPI backend the web app talks to; no retrieval,
generation, or extraction logic is duplicated. See
`docs/adr/0011-mcp-exposure.md` for why, and what's explicitly out of
scope (no MCP-side auth).

This section is a working draft written during Phase 8, while the setup
is fresh -- Phase 11 folds it into the README's final structure (see
`CLAUDE.md` Section 10).

### Run it

The backend must already be running (`docker compose up`, or `uvicorn
app.main:app` from `apps/api`) before an MCP host spawns the server --
the MCP server has nothing to talk to otherwise.

```bash
cd apps/mcp_server
python3.12 -m venv .venv
.venv/bin/pip install -e .
```

You normally don't run the server directly -- an MCP host spawns it over
stdio using the registration below. To sanity-check it standalone:

```bash
MERIDIAN_API_BASE_URL=http://localhost:8000 .venv/bin/python -m mcp_server
```

### Register with Claude Code

A project-scoped `.mcp.json` is already checked into the repo root, using
`${CLAUDE_PROJECT_DIR}` so it works regardless of where the repo is
cloned:

```json
{
  "mcpServers": {
    "meridian": {
      "command": "${CLAUDE_PROJECT_DIR}/apps/mcp_server/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "env": {
        "MERIDIAN_API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

Open the repo in Claude Code and accept the project-MCP-server trust
prompt; no further setup needed as long as `apps/mcp_server/.venv` exists
(see "Run it" above).

Or register it one-off, without relying on the checked-in file:

```bash
claude mcp add --transport stdio meridian \
  --env MERIDIAN_API_BASE_URL=http://localhost:8000 \
  -- /absolute/path/to/apps/mcp_server/.venv/bin/python -m mcp_server
```

### Register with Claude Desktop

Add to `claude_desktop_config.json` (Claude Desktop does not expand
`${CLAUDE_PROJECT_DIR}`, so this needs a real absolute path, and `type`
is required):

```json
{
  "mcpServers": {
    "meridian": {
      "type": "stdio",
      "command": "/absolute/path/to/apps/mcp_server/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "env": {
        "MERIDIAN_API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```
