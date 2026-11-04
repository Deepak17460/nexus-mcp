import httpx
import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_health_check_available_and_authenticated(nexus_client):
    """A 200 /v1/status (empty body) plus a successful repositories call.

    /v1/status never returns a JSON body in real Nexus — this must not call
    response.json() on it.
    """
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/status").mock(
            return_value=Response(200)
        )
        respx.get("http://localhost:8081/service/rest/v1/repositories").mock(
            return_value=Response(200, json=[])
        )

        result = await nexus_client.health_check()

        assert result["available"] is True
        assert result["status_code"] == 200
        assert result["auth_valid"] is True
        assert result["auth_error"] is None
        assert "edition" not in result
        assert "version" not in result


@pytest.mark.asyncio
async def test_health_check_unavailable_when_status_503(nexus_client):
    """A 503 from /v1/status means Nexus can't currently serve reads."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/status").mock(
            return_value=Response(503)
        )
        respx.get("http://localhost:8081/service/rest/v1/repositories").mock(
            return_value=Response(200, json=[])
        )

        result = await nexus_client.health_check()

        assert result["available"] is False
        assert result["status_code"] == 503


@pytest.mark.asyncio
async def test_health_check_detects_invalid_credentials(nexus_client):
    """A 401/403 from the repositories probe means auth_valid=False, not a crash.

    /v1/status itself requires no authentication, so it alone can't tell us
    whether the configured credentials are valid.
    """
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/status").mock(
            return_value=Response(200)
        )
        respx.get("http://localhost:8081/service/rest/v1/repositories").mock(
            return_value=Response(401)
        )

        result = await nexus_client.health_check()

        assert result["available"] is True
        assert result["auth_valid"] is False
        assert "401" in result["auth_error"]


@pytest.mark.asyncio
async def test_health_check_status_connection_error_propagates(nexus_client):
    """A connection failure on /v1/status itself is a real error, not swallowed."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/status").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with pytest.raises(httpx.HTTPError):
            await nexus_client.health_check()


@pytest.mark.asyncio
async def test_check_writable_true(nexus_client):
    """A 200 response means the node is writable."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/status/writable").mock(
            return_value=Response(200)
        )

        result = await nexus_client.check_writable()
        assert result == {"writable": True, "status_code": 200}


@pytest.mark.asyncio
async def test_check_writable_false_when_read_only(nexus_client):
    """A non-200 response (e.g. HA passive node) means not writable."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/status/writable").mock(
            return_value=Response(403)
        )

        result = await nexus_client.check_writable()
        assert result == {"writable": False, "status_code": 403}
