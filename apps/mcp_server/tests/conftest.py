from collections.abc import AsyncGenerator

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_server.server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client_session() -> AsyncGenerator[ClientSession]:
    """A ClientSession talking to the real `mcp` server object over an
    in-memory transport (no subprocess, no stdio) -- see
    docs/testing.md in the MCP Python SDK. Each tool call still goes out
    over real HTTP to whatever backend MERIDIAN_API_BASE_URL points at;
    only the client-to-MCP-server hop is in-memory.
    """
    async with create_connected_server_and_client_session(mcp, raise_exceptions=True) as session:
        yield session
