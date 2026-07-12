"""Thin async HTTP client over the Meridian FastAPI backend.

Every MCP tool in server.py calls a method here, and every method here is
one HTTP call to an existing backend endpoint (GET /search, POST /ask or
POST /meetings/{id}/ask, GET /action-items) -- no retrieval, generation, or
extraction logic is duplicated from apps/api. See docs/adr/0011.
"""

from typing import Any, cast

import httpx

from mcp_server.config import Settings


class MeridianAPIError(RuntimeError):
    """Raised when the Meridian backend returns a non-2xx response, with the
    backend's own error detail folded into the message -- so a tool failure
    surfaces the same reason a human calling the REST API directly would see,
    not just an HTTP status code.
    """


def _raise_for_backend_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    raise MeridianAPIError(f"{response.status_code} from {response.request.url}: {detail}")


class MeridianClient:
    """Holds no persistent connection: each call opens its own
    `httpx.AsyncClient` for the duration of that one request. An MCP tool
    call happens at conversational pace, not high throughput, so the
    per-call connection cost is negligible -- and it sidesteps a real
    footgun a persistent client would have here: `httpx.AsyncClient`
    (like anything built on asyncio transports) binds to whichever event
    loop is running when it first makes a request, so a single
    long-lived instance breaks with "Event loop is closed" the moment
    it's reused from a different loop (exactly what happens across
    independent test functions, each run in their own loop).
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.meridian_api_base_url
        self._timeout = settings.request_timeout_seconds

    async def search(
        self,
        *,
        query: str,
        top_k: int | None = None,
        meeting_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"query": query}
        if top_k is not None:
            params["top_k"] = top_k
        if meeting_id is not None:
            params["meeting_id"] = meeting_id
        async with self._session() as http:
            response = await http.get("/search", params=params)
        _raise_for_backend_error(response)
        return cast(dict[str, Any], response.json())

    async def ask(self, *, question: str, meeting_id: str | None = None) -> dict[str, Any]:
        path = f"/meetings/{meeting_id}/ask" if meeting_id is not None else "/ask"
        async with self._session() as http:
            response = await http.post(path, json={"question": question})
        _raise_for_backend_error(response)
        return cast(dict[str, Any], response.json())

    async def list_action_items(
        self,
        *,
        status: str | None = None,
        owner: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if owner is not None:
            params["owner"] = owner
        async with self._session() as http:
            response = await http.get("/action-items", params=params)
        _raise_for_backend_error(response)
        return cast(list[dict[str, Any]], response.json())

    def _session(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
