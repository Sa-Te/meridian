"""Entry point: `python -m mcp_server` (or the `meridian-mcp-server`
console script). Runs over stdio, the transport Claude Desktop/Claude Code
expect for a locally-spawned MCP server -- see the README setup section
for the client config.
"""

from mcp_server.server import mcp


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
