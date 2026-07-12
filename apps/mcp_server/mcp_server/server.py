"""MCP server exposing the Meridian backend's search/ask/action-item
lookups as tools, so an MCP host (Claude Desktop, Claude Code) can query
past meeting transcripts directly. Every tool below is a thin wrapper
around MeridianClient (client.py) -- an HTTP call to the existing FastAPI
backend, never a reimplementation of retrieval, generation, or extraction
logic. See docs/adr/0011.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.client import MeridianClient
from mcp_server.config import get_settings

mcp = FastMCP("meridian")
_client = MeridianClient(get_settings())


@mcp.tool()
async def search_meetings(query: str, top_k: int = 8) -> dict[str, Any]:
    """Search past meeting transcripts for chunks relevant to a query.

    Returns up to `top_k` ranked chunks (speaker, timestamps, text, and a
    fused relevance score), each identifying the meeting it came from.
    Use this to find *where* a topic was discussed without generating an
    answer -- for a direct, cited answer to a question, use ask_meetings
    instead.
    """
    return await _client.search(query=query, top_k=top_k)


@mcp.tool()
async def ask_meetings(question: str, meeting_id: str | None = None) -> dict[str, Any]:
    """Ask a natural-language question about past meetings and get a
    cited, generated answer.

    Scopes to one meeting if `meeting_id` is given, otherwise searches
    across every ingested meeting. The answer is declined
    (`supported: false`, with no citations) rather than guessed if
    retrieval doesn't find strong enough supporting evidence.
    """
    return await _client.ask(question=question, meeting_id=meeting_id)


@mcp.tool()
async def get_action_items(
    status: str | None = None,
    owner: str | None = None,
) -> dict[str, Any]:
    """List action items extracted from past meetings.

    Optionally filtered by `status` ('open', 'in_progress', or 'done')
    and/or `owner` (an exact participant name).
    """
    items = await _client.list_action_items(status=status, owner=owner)
    return {"action_items": items}
