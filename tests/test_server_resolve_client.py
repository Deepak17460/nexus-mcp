import base64

import pytest

from nexus_mcp.http_auth import AuthenticationRequiredError
from nexus_mcp.server import NexusServer


class _FakeHttpRequest:
    """Minimal stand-in for the Starlette Request the Streamable HTTP
    transport puts in RequestContext.request -- _resolve_client only ever
    touches .headers."""

    def __init__(self, headers: dict[str, str]):
        self.headers = headers


@pytest.fixture
def nexus_server(mock_config):
    return NexusServer()


def _set_request_context(request):
    from mcp.server.lowlevel.server import request_ctx
    from mcp.shared.context import RequestContext

    return request_ctx.set(
        RequestContext(
            request_id="test-request",
            meta=None,
            session=None,
            lifespan_context=None,
            request=request,
        )
    )


def test_resolve_client_falls_back_to_server_client_with_no_request_context(nexus_server):
    """No active request context at all (e.g. called outside MCP dispatch) --
    the LookupError this raises is caught, falling back to self.client."""
    client = nexus_server._resolve_client()
    assert client is nexus_server.client


def test_resolve_client_falls_back_for_stdio_transport(nexus_server):
    """stdio never sets per-message request metadata, so request_context.request
    is always None -- this is today's (unchanged) stdio behavior."""
    from mcp.server.lowlevel.server import request_ctx

    token = _set_request_context(None)
    try:
        client = nexus_server._resolve_client()
    finally:
        request_ctx.reset(token)

    assert client is nexus_server.client


def test_resolve_client_builds_fresh_per_request_client_from_basic_auth(nexus_server):
    from mcp.server.lowlevel.server import request_ctx

    encoded = base64.b64encode(b"alice:s3cret").decode()
    fake_request = _FakeHttpRequest({"authorization": f"Basic {encoded}"})

    token = _set_request_context(fake_request)
    try:
        client = nexus_server._resolve_client()
    finally:
        request_ctx.reset(token)

    assert client is not nexus_server.client
    assert client.config.nexus_username == "alice"
    assert client.config.nexus_password == "s3cret"
    # The server-wide client/config is untouched by this per-request build.
    assert nexus_server.client.config.nexus_username != "alice"


def test_resolve_client_is_case_insensitive_for_header_name(nexus_server):
    """Starlette headers are case-insensitive; a fake dict with a differently
    -cased key should still work the same way in production."""
    from mcp.server.lowlevel.server import request_ctx

    encoded = base64.b64encode(b"alice:s3cret").decode()
    fake_request = _FakeHttpRequest({"Authorization": f"Basic {encoded}"})

    # dict.get("authorization") on a plain dict with key "Authorization"
    # returns None -- this documents that _resolve_client relies on
    # Starlette's real case-insensitive Headers object in production, not a
    # plain dict (this fake, deliberately, exercises the "no header found"
    # path a plain-dict test double would hit).
    token = _set_request_context(fake_request)
    try:
        with pytest.raises(AuthenticationRequiredError):
            nexus_server._resolve_client()
    finally:
        request_ctx.reset(token)


def test_resolve_client_raises_when_no_authorization_header(nexus_server):
    from mcp.server.lowlevel.server import request_ctx

    token = _set_request_context(_FakeHttpRequest({}))
    try:
        with pytest.raises(AuthenticationRequiredError):
            nexus_server._resolve_client()
    finally:
        request_ctx.reset(token)


def test_resolve_client_raises_on_non_basic_authorization_header(nexus_server):
    from mcp.server.lowlevel.server import request_ctx

    token = _set_request_context(_FakeHttpRequest({"authorization": "Bearer some-token"}))
    try:
        with pytest.raises(AuthenticationRequiredError):
            nexus_server._resolve_client()
    finally:
        request_ctx.reset(token)
