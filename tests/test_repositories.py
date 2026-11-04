import pytest
import respx
from httpx import Response

from nexus_mcp.models import RepositoryOwnerInput
from nexus_mcp.tools.repositories import get_repository_owner


@pytest.mark.asyncio
async def test_list_repositories(nexus_client):
    """Test listing repositories."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/repositories").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "name": "maven-releases",
                        "format": "maven2",
                        "type": "hosted",
                        "online": True,
                        "url": "http://localhost:8081/repository/maven-releases",
                    },
                    {
                        "name": "npm-releases",
                        "format": "npm",
                        "type": "hosted",
                        "online": True,
                        "url": "http://localhost:8081/repository/npm-releases",
                    },
                ],
            )
        )

        repos = await nexus_client.list_repositories()
        assert len(repos) == 2
        assert repos[0].name == "maven-releases"
        assert repos[0].format == "maven2"
        assert repos[0].type == "hosted"
        assert repos[0].online is True
        assert repos[1].name == "npm-releases"


@pytest.mark.asyncio
async def test_get_repository(nexus_client):
    """Test getting a specific repository."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/repositories/maven-releases").mock(
            return_value=Response(
                200,
                json={
                    "name": "maven-releases",
                    "format": "maven2",
                    "type": "hosted",
                    "online": True,
                    "url": "http://localhost:8081/repository/maven-releases",
                    "storage": {
                        "blobStoreName": "default",
                        "strictContentTypeValidation": True,
                    },
                },
            )
        )

        repo = await nexus_client.get_repository("maven-releases")
        assert repo["name"] == "maven-releases"
        assert repo["format"] == "maven2"
        assert repo["storage"]["blobStoreName"] == "default"


@pytest.mark.asyncio
async def test_get_repository_owner_success(nexus_client):
    """The tool wraps the portal's JSON data fetch in the standard status/data envelope."""
    json_data = [
        {
            "repository_name": "maven-releases",
            "repository_format": "maven2",
            "repo_type": "hosted",
            "access_type": "Public",
            "info_owner": "owner@example.com",
        }
    ]
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(200, json=json_data)
        )

        result = await get_repository_owner(
            nexus_client, RepositoryOwnerInput(repository="maven-releases")
        )

    assert result["status"] == "success"
    assert result["data"]["found"] is True
    assert result["data"]["owners"] == ["owner@example.com"]
    assert result["data"]["source_url"] == (
        "https://portal.example/nexus-repo-info/repositories.json"
    )


@pytest.mark.asyncio
async def test_get_repository_owner_portal_unreachable(nexus_client):
    """A portal fetch failure surfaces as a normal error envelope, not an exception."""
    with respx.mock:
        respx.get("https://portal.example/nexus-repo-info/repositories.json").mock(
            return_value=Response(503)
        )

        result = await get_repository_owner(
            nexus_client, RepositoryOwnerInput(repository="maven-releases")
        )

    assert result["status"] == "error"
    assert "error" in result


@pytest.mark.asyncio
async def test_get_repository_owner_not_configured(nexus_client):
    """No NEXUS_REPO_INFO_URL set -> a clear error, not a broken request."""
    nexus_client.config.repo_info_portal_url = ""

    result = await get_repository_owner(
        nexus_client, RepositoryOwnerInput(repository="maven-releases")
    )

    assert result["status"] == "error"
    assert "NEXUS_REPO_INFO_URL" in result["error"]
