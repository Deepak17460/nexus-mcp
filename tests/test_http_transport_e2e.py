"""End-to-end check of the hosted HTTP transport: boots the real ASGI app on
a real loopback socket, drives it with the official MCP client SDK exactly
like a real client would, and confirms the outbound call to "Nexus" (a tiny
real fake-Nexus server, also on a real loopback socket) actually used *that
request's* Basic-auth identity rather than any shared/server-wide one.

A real fake-Nexus server is used here instead of respx: respx patches
httpx's transport globally, which conflicts with the concurrent real
sockets this test already needs for the MCP client <-> hosted-server
connection (confirmed while writing this test -- it deadlocks instead of
raising, even with assert_all_mocked=False). Unit tests elsewhere
(test_auth.py, test_http_auth.py, test_server_resolve_client.py) already
cover the individual pieces in isolation with respx; this test exercises
the real wiring between them end to end (StreamableHTTPSessionManager,
Starlette routing, the request-context contextvar).
"""

import asyncio
import base64
import socket
import sys
from typing import Self

import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


class _RunningServer:
    """A real uvicorn server on a real loopback port, torn down on __aexit__."""

    def __init__(self, app):
        self.port = _free_port()
        self._uv_server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        )
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> Self:
        self._task = asyncio.create_task(self._uv_server.serve())
        for _ in range(100):
            if self._uv_server.started:
                return self
            await asyncio.sleep(0.05)
        raise RuntimeError("uvicorn server did not start in time")

    async def __aexit__(self, *exc_info) -> None:
        self._uv_server.should_exit = True
        if self._task is not None:
            await self._task


def _build_fake_nexus_app(received_auth_headers: list[str]):
    """A tiny real Nexus stand-in: records the Authorization header each
    request carried, and answers just enough for nexus_health_check to
    succeed (GET /status, GET /repositories)."""

    async def status(_: Request) -> Response:
        return Response(status_code=200)

    async def repositories(request: Request) -> JSONResponse:
        received_auth_headers.append(request.headers.get("authorization", ""))
        return JSONResponse([])

    return Starlette(
        routes=[
            Route("/service/rest/v1/status", endpoint=status, methods=["GET"]),
            Route("/service/rest/v1/repositories", endpoint=repositories, methods=["GET"]),
        ]
    )


@pytest.fixture
def http_mode_env(monkeypatch):
    """Fresh Config reload with MCP_TRANSPORT=http and no server-wide auth
    -- mirrors the intended hosted deployment. NEXUS_URL is set per-test
    once the fake-Nexus server's real port is known."""
    for key in ["NEXUS_API_TOKEN", "NEXUS_USERNAME", "NEXUS_PASSWORD"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ALLOW_INSECURE", "true")
    monkeypatch.setenv("MCP_TRANSPORT", "http")

    sys.modules.pop("nexus_mcp.config", None)
    yield monkeypatch
    sys.modules.pop("nexus_mcp.config", None)


@pytest.mark.asyncio
async def test_http_transport_end_to_end_uses_per_request_credentials(http_mode_env):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    from nexus_mcp.http_app import build_http_app
    from nexus_mcp.server import NexusServer

    received_auth_headers: list[str] = []
    fake_nexus_app = _build_fake_nexus_app(received_auth_headers)

    async with _RunningServer(fake_nexus_app) as fake_nexus:
        http_mode_env.setenv("NEXUS_URL", f"http://127.0.0.1:{fake_nexus.port}")
        sys.modules.pop("nexus_mcp.config", None)

        server = NexusServer()
        app = build_http_app(server)

        async with _RunningServer(app) as mcp_http:
            encoded = base64.b64encode(b"alice:s3cret").decode()
            headers = {"authorization": f"Basic {encoded}"}

            async with (
                streamablehttp_client(
                    f"http://127.0.0.1:{mcp_http.port}/mcp", headers=headers
                ) as (read_stream, write_stream, _get_session_id),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()
                result = await asyncio.wait_for(
                    session.call_tool("nexus_health_check", {}), timeout=10
                )

    assert result.isError is False
    text = result.content[0].text
    assert '"status": "success"' in text

    # The outbound call to "Nexus" used *this request's* Basic-auth
    # credentials (alice:s3cret) -- there is no server-wide identity
    # configured at all in http_mode_env, so this can only have come from
    # the per-request Authorization header.
    assert received_auth_headers == [f"Basic {encoded}"]


@pytest.mark.asyncio
async def test_http_transport_rejects_call_with_no_authorization_header(http_mode_env):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    from nexus_mcp.http_app import build_http_app
    from nexus_mcp.server import NexusServer

    http_mode_env.setenv("NEXUS_URL", "http://127.0.0.1:1")  # never dialed -- rejected first
    sys.modules.pop("nexus_mcp.config", None)

    server = NexusServer()
    app = build_http_app(server)

    async with (
        _RunningServer(app) as mcp_http,
        streamablehttp_client(f"http://127.0.0.1:{mcp_http.port}/mcp") as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        result = await asyncio.wait_for(
            session.call_tool("nexus_health_check", {}), timeout=10
        )

    # Rejected at the tool level (a clean {"error": ...} payload), not a
    # transport/protocol-level failure, and never silently proceeds with
    # some default identity (there is none configured here anyway).
    assert result.isError is False
    text = result.content[0].text
    assert "Authorization" in text


@pytest.mark.asyncio
async def test_http_transport_healthz_requires_no_auth(http_mode_env):
    """The liveness probe works even with zero Nexus credentials configured."""
    import httpx

    http_mode_env.setenv("NEXUS_URL", "http://127.0.0.1:1")
    sys.modules.pop("nexus_mcp.config", None)

    from nexus_mcp.http_app import build_http_app
    from nexus_mcp.server import NexusServer

    server = NexusServer()
    app = build_http_app(server)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
