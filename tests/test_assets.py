import base64

import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_download_asset_returns_base64(nexus_client):
    """Downloading without save_path returns bounded base64 content."""
    content = b"hello nexus"
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/assets/asset-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "asset-1",
                    "path": "com/example/app/1.0/app-1.0.jar",
                    "checksum": {"sha1": "abc123"},
                    "downloadUrl": "http://localhost:8081/repository/maven-releases/app-1.0.jar",
                },
            )
        )
        respx.get(
            "http://localhost:8081/repository/maven-releases/app-1.0.jar"
        ).mock(return_value=Response(200, content=content))

        result = await nexus_client.download_asset("asset-1")

        assert result["asset_id"] == "asset-1"
        assert result["size_bytes"] == len(content)
        assert base64.b64decode(result["content_base64"]) == content
        assert "saved_to" not in result


@pytest.mark.asyncio
async def test_download_asset_saves_to_path(nexus_client, tmp_path):
    """Downloading with save_path streams content to disk."""
    content = b"binary artifact content"
    dest = tmp_path / "downloaded.bin"
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/assets/asset-2").mock(
            return_value=Response(
                200,
                json={
                    "id": "asset-2",
                    "path": "raw/artifact.bin",
                    "downloadUrl": "http://localhost:8081/repository/raw-hosted/artifact.bin",
                },
            )
        )
        respx.get(
            "http://localhost:8081/repository/raw-hosted/artifact.bin"
        ).mock(return_value=Response(200, content=content))

        result = await nexus_client.download_asset("asset-2", save_path=str(dest))

        assert result["saved_to"] == str(dest)
        assert result["size_bytes"] == len(content)
        assert dest.read_bytes() == content


@pytest.mark.asyncio
async def test_download_asset_enforces_size_cap(nexus_client):
    """Exceeding max_size_bytes aborts with an error, no partial base64."""
    content = b"x" * 100
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/assets/asset-3").mock(
            return_value=Response(
                200,
                json={
                    "id": "asset-3",
                    "path": "raw/big-file.bin",
                    "downloadUrl": "http://localhost:8081/repository/raw-hosted/big-file.bin",
                },
            )
        )
        respx.get(
            "http://localhost:8081/repository/raw-hosted/big-file.bin"
        ).mock(return_value=Response(200, content=content))

        result = await nexus_client.download_asset("asset-3", max_size_bytes=10)

        assert "error" in result
        assert "max_size_bytes" in result["error"]


@pytest.mark.asyncio
async def test_download_asset_missing_download_url(nexus_client):
    """An asset with no downloadUrl returns a clear error instead of raising."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/assets/asset-4").mock(
            return_value=Response(200, json={"id": "asset-4", "path": "no/url"})
        )

        result = await nexus_client.download_asset("asset-4")

        assert result == {"error": "Asset 'asset-4' has no downloadUrl"}


@pytest.mark.asyncio
async def test_get_download_url_by_asset_id(nexus_client):
    """Resolving by asset_id returns the URL without fetching content."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/assets/asset-5").mock(
            return_value=Response(
                200,
                json={
                    "id": "asset-5",
                    "path": "com/example/app/1.0/app-1.0.jar",
                    "downloadUrl": "http://localhost:8081/repository/maven-releases/app-1.0.jar",
                    "fileSize": 42,
                },
            )
        )

        result = await nexus_client.get_download_url(asset_id="asset-5")

        assert result["match_count"] == 1
        assert result["matches"][0]["download_url"] == (
            "http://localhost:8081/repository/maven-releases/app-1.0.jar"
        )
        # No request should have been made to the download URL itself.
        assert not respx.calls.last.request.url.path.endswith("app-1.0.jar")


@pytest.mark.asyncio
async def test_get_download_url_by_coordinates(nexus_client):
    """Resolving by repository + name searches assets and returns matches."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search/assets").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": "asset-6",
                            "path": "raw/artifact.bin",
                            "downloadUrl": "http://localhost:8081/repository/raw-hosted/artifact.bin",
                            "fileSize": 100,
                        }
                    ],
                    "continuationToken": None,
                },
            )
        )

        result = await nexus_client.get_download_url(repository="raw-hosted", name="artifact")

        assert result["match_count"] == 1
        assert result["matches"][0]["asset_id"] == "asset-6"


@pytest.mark.asyncio
async def test_get_download_url_no_matches_returns_error(nexus_client):
    """No matching assets returns a clear error, not an empty success."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search/assets").mock(
            return_value=Response(200, json={"items": []})
        )

        result = await nexus_client.get_download_url(repository="raw-hosted", name="missing")

        assert "error" in result


@pytest.mark.asyncio
async def test_get_download_url_requires_asset_id_or_coordinates(nexus_client):
    """Neither asset_id nor repository+name provided returns a usage error."""
    result = await nexus_client.get_download_url()

    assert result == {"error": "Provide either asset_id, or repository and name"}
