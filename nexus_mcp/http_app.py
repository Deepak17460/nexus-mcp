"""ASGI app for running the Nexus MCP server over Streamable HTTP.

Only used when ``MCP_TRANSPORT=http`` (see ``main.py``). Tool dispatch logic
is identical to the stdio transport — only the transport differs. Every
request must carry its own
``Authorization: Basic <base64(username:password)>`` header with the
caller's own Nexus credentials (see ``NexusServer._resolve_client()`` in
``server.py`` / ``http_auth.py``); this module adds no credential handling
of its own.

This process is expected to sit behind a TLS-terminating reverse proxy
(nginx, etc.) — it listens on plain HTTP internally, matching how the rest
of this org's Nexus deployment is already fronted. See the README's
"Hosted / Multi-user Deployment" section before exposing this directly.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from nexus_mcp.server import NexusServer


class _StreamableHTTPASGIApp:
    """Thin ASGI-app wrapper around a ``StreamableHTTPSessionManager``.

    Deliberately a callable *object*, not a plain ``async def`` function:
    Starlette's ``Route`` only treats an endpoint as a raw ASGI app when
    ``inspect.isfunction()``/``inspect.ismethod()`` are both false for it --
    otherwise it wraps the endpoint as a ``(Request) -> Response`` handler
    via ``request_response()``, which does not match this callable's
    ``(scope, receive, send)`` signature. This mirrors the MCP SDK's own
    ``mcp.server.fastmcp.server.StreamableHTTPASGIApp``.

    Mounted via ``Route`` (not ``Mount``) on purpose too: a ``Mount`` at
    "/mcp" 307-redirects a bare "/mcp" request to "/mcp/" (Starlette's
    default ``redirect_slashes`` behavior for sub-apps), and since this
    process only ever sees plain HTTP from behind a TLS-terminating proxy
    (see module docstring), that redirect's Location header is built as
    ``http://`` instead of ``https://`` -- a scheme downgrade most MCP
    clients refuse to follow, which silently breaks every connection. A
    ``Route`` matches the exact literal path with no such redirect.
    """

    def __init__(self, session_manager: StreamableHTTPSessionManager) -> None:
        self._session_manager = session_manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._session_manager.handle_request(scope, receive, send)


def build_http_app(nexus_server: NexusServer) -> Starlette:
    """Build the Starlette ASGI app exposing ``nexus_server`` over Streamable HTTP.

    Uses ``stateless=True``: every request gets a fresh transport with no
    server-side MCP session tracking between requests. That matches this
    deployment's per-request Basic-auth model — there's no session/identity
    to persist or accidentally leak between different callers.
    """
    session_manager = StreamableHTTPSessionManager(app=nexus_server.server, stateless=True)
    handle_mcp = _StreamableHTTPASGIApp(session_manager)

    async def healthz(_: Request) -> JSONResponse:
        # Liveness probe only — touches no Nexus credentials or endpoints,
        # so it works even with no server-wide auth configured (see
        # Config._validate for MCP_TRANSPORT=http).
        return JSONResponse({"status": "ok"})

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/healthz", endpoint=healthz, methods=["GET"]),
            # No `methods=` restriction, matching the MCP SDK's own
            # reference wiring (mcp.server.fastmcp.server.streamable_http_app)
            # -- the session manager itself handles GET (SSE stream), POST
            # (JSON-RPC messages), DELETE (session termination), and OPTIONS
            # (CORS preflight); restricting methods here would 405 whichever
            # ones aren't listed.
            Route("/mcp", endpoint=handle_mcp),
        ],
        lifespan=lifespan,
    )
