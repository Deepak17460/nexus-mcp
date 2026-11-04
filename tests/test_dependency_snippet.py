import pytest
import respx
from httpx import Response

from nexus_mcp.models import DependencySnippetInput
from nexus_mcp.tools.components import (
    _build_dependency_snippets,
    get_dependency_snippet,
)


def test_build_dependency_snippets_maven():
    snippets, notes = _build_dependency_snippets(
        format="maven2",
        repository="maven-releases",
        nexus_url="http://localhost:8081",
        group="com.example",
        name="app",
        version="1.2.0",
        download_url="http://localhost:8081/repository/maven-releases/app-1.2.0.jar",
    )

    assert "<groupId>com.example</groupId>" in snippets["maven_dependency"]
    assert "<version>1.2.0</version>" in snippets["maven_dependency"]
    assert "maven-releases" in snippets["maven_repository"]
    assert 'implementation "com.example:app:1.2.0"' == snippets["gradle_dependency"]
    assert snippets["direct_url"].endswith("app-1.2.0.jar")
    assert any("settings.xml" in n for n in notes)


def test_build_dependency_snippets_npm():
    snippets, _ = _build_dependency_snippets(
        format="npm",
        repository="npm-hosted",
        nexus_url="http://localhost:8081",
        group=None,
        name="left-pad",
        version="1.3.0",
        download_url=None,
    )

    assert snippets["npm_install"] == (
        "npm install left-pad@1.3.0 --registry=http://localhost:8081/repository/npm-hosted/"
    )
    assert "registry=" in snippets["npm_registry"]
    assert "direct_url" not in snippets  # no download_url provided


def test_build_dependency_snippets_unknown_format_falls_back_to_direct_url():
    snippets, notes = _build_dependency_snippets(
        format="conda",
        repository="conda-hosted",
        nexus_url="http://localhost:8081",
        group=None,
        name="pkg",
        version="1.0.0",
        download_url="http://localhost:8081/repository/conda-hosted/pkg-1.0.0.tar.bz2",
    )

    assert snippets["direct_url"].endswith("pkg-1.0.0.tar.bz2")
    assert any("No dedicated build-tool template" in n for n in notes)


@pytest.mark.asyncio
async def test_get_dependency_snippet_auto_resolves_latest(nexus_client):
    """Omitting version/format triggers an auto-resolve via get_latest_release."""
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
                            "version": "3.4.0",
                            "format": "maven2",
                            "assets": [
                                {
                                    "downloadUrl": "http://localhost:8081/repository/maven-releases/app-3.4.0.jar",
                                }
                            ],
                        }
                    ]
                },
            )
        )
        respx.get("http://localhost:8081/service/rest/v1/repositories/maven-releases").mock(
            return_value=Response(
                200,
                json={
                    "name": "maven-releases",
                    "format": "maven2",
                    "type": "hosted",
                    "url": "http://localhost:8081/repository/maven-releases",
                },
            )
        )

        result = await get_dependency_snippet(
            nexus_client,
            DependencySnippetInput(repository="maven-releases", name="app"),
        )

        assert result["status"] == "success"
        assert result["data"]["version"] == "3.4.0"
        assert result["data"]["group"] == "com.example"
        assert result["data"]["repository_url"] == "http://localhost:8081/repository/maven-releases"
        assert "access_help" in result["data"]
        assert "maven_dependency" in result["data"]["snippets"]


@pytest.mark.asyncio
async def test_get_dependency_snippet_filters_by_build_tool(nexus_client):
    """build_tool restricts the snippet set to matching keys."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/repositories/npm-hosted").mock(
            return_value=Response(
                200,
                json={
                    "name": "npm-hosted",
                    "format": "npm",
                    "type": "hosted",
                    "url": "http://localhost:8081/repository/npm-hosted",
                },
            )
        )

        result = await get_dependency_snippet(
            nexus_client,
            DependencySnippetInput(
                repository="npm-hosted",
                name="left-pad",
                version="1.3.0",
                format="npm",
                build_tool="npm",
            ),
        )

        assert result["status"] == "success"
        assert set(result["data"]["snippets"]).issubset(
            {"npm_install", "npm_registry", "npm_package_json", "direct_url", "curl_download"}
        )


@pytest.mark.asyncio
async def test_get_dependency_snippet_docker_prefers_path_based_routing(nexus_client):
    """docker.pathEnabled wins over a connector port — this is what works behind
    a reverse proxy (e.g. nginx) that only exposes HTTPS."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/repositories/docker-hosted").mock(
            return_value=Response(
                200,
                json={
                    "name": "docker-hosted",
                    "format": "docker",
                    "type": "hosted",
                    "url": "http://localhost:8081/repository/docker-hosted",
                },
            )
        )
        respx.get(
            "http://localhost:8081/service/rest/v1/repositories/docker/hosted/docker-hosted"
        ).mock(
            return_value=Response(
                200,
                json={"docker": {"httpPort": 9005, "pathEnabled": True}},
            )
        )

        result = await get_dependency_snippet(
            nexus_client,
            DependencySnippetInput(
                repository="docker-hosted", name="my-app", version="1.0.0", format="docker"
            ),
        )

        assert result["status"] == "success"
        assert result["data"]["snippets"]["docker_pull"] == (
            "docker pull localhost:8081/repository/docker-hosted/my-app:1.0.0"
        )
        assert result["data"]["snippets"]["docker_login"] == "docker login localhost:8081"
        assert any("path-based Docker routing" in n for n in result["data"]["notes"])
        assert any("also configured at localhost:9005" in n for n in result["data"]["notes"])


@pytest.mark.asyncio
async def test_get_dependency_snippet_docker_uses_connector_when_no_path_routing(nexus_client):
    """Without pathEnabled, falls back to the dedicated connector host:port."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/repositories/docker-hosted").mock(
            return_value=Response(
                200,
                json={
                    "name": "docker-hosted",
                    "format": "docker",
                    "type": "hosted",
                    "url": "http://localhost:8081/repository/docker-hosted",
                },
            )
        )
        respx.get(
            "http://localhost:8081/service/rest/v1/repositories/docker/hosted/docker-hosted"
        ).mock(
            return_value=Response(
                200,
                json={"docker": {"httpPort": 8082, "httpsPort": None, "pathEnabled": False}},
            )
        )

        result = await get_dependency_snippet(
            nexus_client,
            DependencySnippetInput(
                repository="docker-hosted", name="my-app", version="1.0.0", format="docker"
            ),
        )

        assert result["status"] == "success"
        assert result["data"]["snippets"]["docker_pull"] == "docker pull localhost:8082/my-app:1.0.0"
        assert result["data"]["snippets"]["docker_login"] == "docker login localhost:8082"
        assert any(
            "reverse proxy that only exposes HTTPS/443" in n for n in result["data"]["notes"]
        )


@pytest.mark.asyncio
async def test_get_dependency_snippet_docker_falls_back_without_connector(nexus_client):
    """Docker format with neither path routing nor a connector port falls back
    to a placeholder note."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/repositories/docker-hosted").mock(
            return_value=Response(
                200,
                json={
                    "name": "docker-hosted",
                    "format": "docker",
                    "type": "hosted",
                    "url": "http://localhost:8081/repository/docker-hosted",
                },
            )
        )
        respx.get(
            "http://localhost:8081/service/rest/v1/repositories/docker/hosted/docker-hosted"
        ).mock(
            return_value=Response(
                200, json={"docker": {"httpPort": None, "httpsPort": None, "pathEnabled": False}}
            )
        )

        result = await get_dependency_snippet(
            nexus_client,
            DependencySnippetInput(
                repository="docker-hosted", name="my-app", version="1.0.0", format="docker"
            ),
        )

        assert result["status"] == "success"
        assert "<docker-connector-host>" in result["data"]["snippets"]["docker_pull"]
        assert any(
            "neither path-based routing nor an HTTP/HTTPS connector port" in n
            for n in result["data"]["notes"]
        )


@pytest.mark.asyncio
async def test_get_dependency_snippet_no_candidates_returns_error(nexus_client):
    """If auto-resolve finds nothing, a clear error is returned (not a crash)."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search").mock(
            return_value=Response(200, json={"items": []})
        )

        result = await get_dependency_snippet(
            nexus_client,
            DependencySnippetInput(repository="maven-releases", name="missing"),
        )

        assert result["status"] == "error"
