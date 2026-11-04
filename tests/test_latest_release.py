import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_get_latest_release_by_name_excludes_snapshots(nexus_client):
    """When name is given, the highest non-snapshot version is returned."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": "c1",
                            "group": "com.example",
                            "name": "app",
                            "version": "1.2.0",
                            "format": "maven2",
                            "assets": [
                                {
                                    "id": "a1",
                                    "path": "com/example/app/1.2.0/app-1.2.0.jar",
                                    "downloadUrl": "http://localhost:8081/repository/maven-releases/app-1.2.0.jar",
                                    "fileSize": 100,
                                }
                            ],
                        },
                        {
                            "id": "c2",
                            "group": "com.example",
                            "name": "app",
                            "version": "1.3.0-SNAPSHOT",
                            "format": "maven2",
                            "assets": [],
                        },
                        {
                            "id": "c3",
                            "group": "com.example",
                            "name": "app",
                            "version": "1.1.0",
                            "format": "maven2",
                            "assets": [],
                        },
                    ]
                },
            )
        )

        result = await nexus_client.get_latest_release(
            repository="maven-releases", name="app"
        )

        assert result["version"] == "1.2.0"
        assert result["component_id"] == "c1"
        assert result["assets"][0]["download_url"].endswith("app-1.2.0.jar")


@pytest.mark.asyncio
async def test_get_latest_release_without_name_picks_most_recent(nexus_client):
    """Without name, the most-recently-published non-snapshot component wins."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": "old",
                            "name": "app-a",
                            "version": "1.0.0",
                            "format": "maven2",
                            "assets": [{"lastModified": "2024-01-01T00:00:00.000Z"}],
                        },
                        {
                            "id": "new",
                            "name": "app-b",
                            "version": "2.0.0",
                            "format": "maven2",
                            "assets": [{"blobCreated": "2024-06-01T00:00:00.000Z"}],
                        },
                    ]
                },
            )
        )

        result = await nexus_client.get_latest_release(repository="maven-releases")

        assert result["name"] == "app-b"
        assert result["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_get_latest_release_no_candidates(nexus_client):
    """No non-snapshot components returns a clear error, not an exception."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search").mock(
            return_value=Response(200, json={"items": []})
        )

        result = await nexus_client.get_latest_release(repository="maven-releases")

        assert "error" in result
