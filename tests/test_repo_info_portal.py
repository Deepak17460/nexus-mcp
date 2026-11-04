import httpx
import pytest
import respx
from httpx import Response

from nexus_mcp.repo_info_portal import RepoInfoPortalError, fetch_repository_owner

# Mirrors the real portal's confirmed data source: the HTML page's <tbody> is
# always empty; a JS fetch('repositories.json') (relative to the portal page)
# supplies the actual rows as a JSON list with these field names.
_SAMPLE_JSON = [
    {
        "repository_name": "in-house",
        "repository_format": "maven2",
        "repo_type": "hosted",
        "access_type": "Public",
        "info_owner": (
            "alice.example@example.com, bob.example@example.com, "
            "carol.example@example.com"
        ),
    },
    {
        "repository_name": "test-poc",
        "repository_format": "maven2",
        "repo_type": "proxy",
        "access_type": "private",
        "info_owner": "dave.example@example.com",
    },
]


@pytest.mark.asyncio
async def test_fetch_repository_owner_single_owner():
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(200, json=_SAMPLE_JSON)
        )

        result = await fetch_repository_owner(
            "https://portal.example/nexus-repo-info/", "test-poc"
        )

    assert result == {
        "found": True,
        "repository": "test-poc",
        "format": "maven2",
        "type": "proxy",
        "access": "private",
        "owners": ["dave.example@example.com"],
        "source_url": "https://portal.example/nexus-repo-info/repositories.json",
    }


@pytest.mark.asyncio
async def test_fetch_repository_owner_multiple_owners():
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(200, json=_SAMPLE_JSON)
        )

        result = await fetch_repository_owner(
            "https://portal.example/nexus-repo-info/", "in-house"
        )

    assert result["found"] is True
    assert result["owners"] == [
        "alice.example@example.com",
        "bob.example@example.com",
        "carol.example@example.com",
    ]


@pytest.mark.asyncio
async def test_fetch_repository_owner_is_case_insensitive():
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(200, json=_SAMPLE_JSON)
        )

        result = await fetch_repository_owner(
            "https://portal.example/nexus-repo-info/", "TEST-POC"
        )

    assert result["found"] is True
    assert result["access"] == "private"


@pytest.mark.asyncio
async def test_fetch_repository_owner_resolves_relative_url_without_trailing_slash():
    """portal_url with no trailing slash still resolves repositories.json the
    same way the browser's relative fetch() would (same directory, not a
    sibling of the portal path segment)."""
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(200, json=_SAMPLE_JSON)
        )

        result = await fetch_repository_owner(
            "https://portal.example/nexus-repo-info", "test-poc"
        )

    assert result["found"] is True
    assert result["source_url"] == "https://portal.example/nexus-repo-info/repositories.json"


@pytest.mark.asyncio
async def test_fetch_repository_owner_not_in_data():
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(200, json=_SAMPLE_JSON)
        )

        result = await fetch_repository_owner(
            "https://portal.example/nexus-repo-info/", "does-not-exist"
        )

    assert result == {
        "found": False,
        "repository": "does-not-exist",
        "source_url": "https://portal.example/nexus-repo-info/repositories.json",
    }


@pytest.mark.asyncio
async def test_fetch_repository_owner_data_not_a_list():
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(200, json={"error": "not a list"})
        )

        result = await fetch_repository_owner(
            "https://portal.example/nexus-repo-info/", "test-poc"
        )

    assert result["found"] is False
    assert "parse_note" in result


@pytest.mark.asyncio
async def test_fetch_repository_owner_raises_on_network_error():
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with pytest.raises(RepoInfoPortalError):
            await fetch_repository_owner(
                "https://portal.example/nexus-repo-info/", "test-poc"
            )


@pytest.mark.asyncio
async def test_fetch_repository_owner_raises_on_http_error_status():
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(503, text="unavailable")
        )

        with pytest.raises(RepoInfoPortalError):
            await fetch_repository_owner(
                "https://portal.example/nexus-repo-info/", "test-poc"
            )


@pytest.mark.asyncio
async def test_fetch_repository_owner_raises_on_invalid_json():
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(200, text="not json")
        )

        with pytest.raises(RepoInfoPortalError):
            await fetch_repository_owner(
                "https://portal.example/nexus-repo-info/", "test-poc"
            )
