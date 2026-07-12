"""Smoke tests: invoke each MCP tool through the real MCP protocol
(in-memory client/server transport, see conftest.py) against a running
Meridian backend, and assert a well-formed response. Requires
MERIDIAN_API_BASE_URL (default http://localhost:8000) to point at a live,
migrated backend -- see ROADMAP.md Phase 8's definition of done.

Deliberately content-agnostic (no assertion on *which* meetings/action
items come back): the backend this runs against may have zero or many
ingested meetings depending on where it runs (a fresh CI database vs. a
developer's own populated local one), and retrieval/generation quality
itself is already covered by apps/api's own test suite and eval/. This
suite only proves the tool-to-backend wiring produces a well-formed
response either way.
"""

from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.types import CallToolResult


def _structured_content(result: CallToolResult) -> dict[str, Any]:
    assert result.isError is False, result.content
    assert result.structuredContent is not None
    return result.structuredContent


@pytest.mark.anyio
async def test_search_meetings_returns_well_formed_results(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool(
        "search_meetings", {"query": "workout feedback schema", "top_k": 3}
    )

    body = _structured_content(result)
    assert isinstance(body["results"], list)
    for item in body["results"]:
        citation = item["citation"]
        assert isinstance(item["fused_score"], float)
        assert {"chunk_id", "meeting_id", "speaker", "start_ts", "end_ts", "text"} <= set(citation)


@pytest.mark.anyio
async def test_ask_meetings_returns_well_formed_answer(client_session: ClientSession) -> None:
    result = await client_session.call_tool(
        "ask_meetings", {"question": "What is the capital of France?"}
    )

    body = _structured_content(result)
    assert isinstance(body["answer"], str)
    assert isinstance(body["supported"], bool)
    assert isinstance(body["citations"], list)


@pytest.mark.anyio
async def test_ask_meetings_scoped_to_unknown_meeting_surfaces_as_tool_error(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool(
        "ask_meetings",
        {"question": "Anything?", "meeting_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert result.isError is True


@pytest.mark.anyio
async def test_get_action_items_returns_well_formed_list(client_session: ClientSession) -> None:
    result = await client_session.call_tool("get_action_items", {})

    body = _structured_content(result)
    assert isinstance(body["action_items"], list)
    for item in body["action_items"]:
        assert {"id", "meeting_id", "text", "status", "source_citation"} <= set(item)


@pytest.mark.anyio
async def test_get_action_items_filters_by_status(client_session: ClientSession) -> None:
    result = await client_session.call_tool("get_action_items", {"status": "open"})

    body = _structured_content(result)
    assert all(item["status"] == "open" for item in body["action_items"])
