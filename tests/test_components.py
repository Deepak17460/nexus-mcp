import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_get_component_versions_sorted_with_latest(nexus_client):
    """Versions are de-duplicated, naturally sorted, and latest is surfaced."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {"version": "1.9.0"},
                        {"version": "1.10.0"},
                        {"version": "1.2.0"},
                        {"version": "1.2.0"},  # duplicate, should be ignored
                    ],
                    "continuationToken": None,
                },
            )
        )

        result = await nexus_client.get_component_versions(
            repository="maven-releases", name="app", group="com.example"
        )

        assert result["version_count"] == 3
        assert result["versions"] == ["1.2.0", "1.9.0", "1.10.0"]
        assert result["latest_version"] == "1.10.0"


@pytest.mark.asyncio
async def test_get_component_versions_paginates(nexus_client):
    """Continuation tokens are followed until exhausted."""
    with respx.mock:
        route = respx.get("http://localhost:8081/service/rest/v1/search")
        route.side_effect = [
            Response(
                200,
                json={"items": [{"version": "1.0.0"}], "continuationToken": "next"},
            ),
            Response(
                200,
                json={"items": [{"version": "2.0.0"}], "continuationToken": None},
            ),
        ]

        result = await nexus_client.get_component_versions(
            repository="maven-releases", name="app"
        )

        assert result["versions"] == ["1.0.0", "2.0.0"]
        assert result["latest_version"] == "2.0.0"


@pytest.mark.asyncio
async def test_get_component_versions_no_matches(nexus_client):
    """No matching components returns an empty list and a None latest_version."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search").mock(
            return_value=Response(200, json={"items": []})
        )

        result = await nexus_client.get_component_versions(
            repository="maven-releases", name="missing-app"
        )

        assert result["versions"] == []
        assert result["latest_version"] is None


@pytest.mark.asyncio
async def test_check_artifact_exists_true_for_exact_version(nexus_client):
    """An exact-version match reports exists=True with the matching component."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": "component-1",
                            "group": "com.example",
                            "name": "app",
                            "version": "1.2.0",
                            "format": "maven2",
                            "assets": [
                                {
                                    "id": "asset-1",
                                    "path": "com/example/app/1.2.0/app-1.2.0.jar",
                                    "downloadUrl": "http://localhost:8081/repository/maven-releases/app-1.2.0.jar",
                                    "fileSize": 1234,
                                }
                            ],
                        }
                    ],
                    "continuationToken": None,
                },
            )
        )

        result = await nexus_client.check_artifact_exists(
            repository="maven-releases", name="app", version="1.2.0", group="com.example"
        )

        assert result["exists"] is True
        assert result["match_count"] == 1
        assert result["matches"][0]["version"] == "1.2.0"
        assert result["matches"][0]["assets"][0]["asset_id"] == "asset-1"


@pytest.mark.asyncio
async def test_check_artifact_exists_false_when_no_matches(nexus_client):
    """No matching components reports exists=False, not an error."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search").mock(
            return_value=Response(200, json={"items": []})
        )

        result = await nexus_client.check_artifact_exists(
            repository="maven-releases", name="app", version="9.9.9"
        )

        assert result["exists"] is False
        assert result["match_count"] == 0
        assert result["matches"] == []


@pytest.mark.asyncio
async def test_check_artifact_exists_without_version_checks_any(nexus_client):
    """Omitting version checks whether any version of the component exists."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {"id": "c1", "name": "app", "version": "1.0.0", "assets": []},
                        {"id": "c2", "name": "app", "version": "2.0.0", "assets": []},
                    ],
                    "continuationToken": None,
                },
            )
        )

        result = await nexus_client.check_artifact_exists(repository="maven-releases", name="app")

        assert result["exists"] is True
        assert result["match_count"] == 2


@pytest.mark.asyncio
async def test_get_docker_pull_info_prefers_https_port_when_no_path_routing(nexus_client):
    """When both ports are configured, the HTTPS connector port wins."""
    repo = {"name": "docker-hosted", "format": "docker", "type": "hosted"}
    with respx.mock:
        respx.get(
            "http://localhost:8081/service/rest/v1/repositories/docker/hosted/docker-hosted"
        ).mock(
            return_value=Response(
                200,
                json={"docker": {"httpPort": 8082, "httpsPort": 8083, "pathEnabled": False}},
            )
        )

        info = await nexus_client.get_docker_pull_info("docker-hosted", repo=repo)

        assert info == {"path_enabled": False, "connector_host": "localhost:8083"}


@pytest.mark.asyncio
async def test_get_docker_pull_info_reports_path_enabled(nexus_client):
    """docker.pathEnabled is surfaced even when a connector port is also configured."""
    repo = {"name": "docker-hosted", "format": "docker", "type": "hosted"}
    with respx.mock:
        respx.get(
            "http://localhost:8081/service/rest/v1/repositories/docker/hosted/docker-hosted"
        ).mock(
            return_value=Response(
                200, json={"docker": {"httpPort": 9005, "pathEnabled": True}}
            )
        )

        info = await nexus_client.get_docker_pull_info("docker-hosted", repo=repo)

        assert info == {"path_enabled": True, "connector_host": "localhost:9005"}


@pytest.mark.asyncio
async def test_get_docker_pull_info_non_docker_repo_returns_none(nexus_client):
    """Non-Docker repositories short-circuit without making a second HTTP call."""
    repo = {"name": "maven-releases", "format": "maven2", "type": "hosted"}
    with respx.mock:
        # No routes mocked — if the client tried to call the network, this
        # would raise respx.AllMockedAssertionError and fail the test.
        info = await nexus_client.get_docker_pull_info("maven-releases", repo=repo)

    assert info is None


@pytest.mark.asyncio
async def test_get_docker_pull_info_fetches_repo_when_not_given(nexus_client):
    """Without a pre-fetched repo dict, it looks the repository up first."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/repositories/docker-hosted").mock(
            return_value=Response(
                200, json={"name": "docker-hosted", "format": "docker", "type": "proxy"}
            )
        )
        respx.get(
            "http://localhost:8081/service/rest/v1/repositories/docker/proxy/docker-hosted"
        ).mock(return_value=Response(200, json={"docker": {"httpPort": 8082}}))

        info = await nexus_client.get_docker_pull_info("docker-hosted")

    assert info == {"path_enabled": False, "connector_host": "localhost:8082"}
