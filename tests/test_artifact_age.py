from datetime import UTC, datetime, timedelta

import pytest
import respx
from httpx import Response


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_artifact_age_report_classifies_and_flags_stale(nexus_client):
    """Snapshot/pre-release/release are classified; old+unused assets are stale."""
    now = datetime.now(UTC)
    old_snapshot = _iso(now - timedelta(days=200))
    recent_release = _iso(now - timedelta(days=1))

    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/assets").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": "a1",
                            "path": "com/example/app/1.0.0-SNAPSHOT/app.jar",
                            "version": "1.0.0-SNAPSHOT",
                            "format": "maven2",
                            "blobCreated": old_snapshot,
                            "fileSize": 100,
                            # never downloaded
                        },
                        {
                            "id": "a2",
                            "path": "com/example/app/2.0.0/app.jar",
                            "version": "2.0.0",
                            "format": "maven2",
                            "blobCreated": recent_release,
                            "lastDownloaded": recent_release,
                            "fileSize": 200,
                        },
                    ]
                },
            )
        )

        result = await nexus_client.get_artifact_age_report(
            repository="maven-releases", stale_after_days=90
        )

        by_id = {item["asset_id"]: item for item in result["oldest_first"]}
        assert by_id["a1"]["classification"] == "snapshot"
        assert by_id["a1"]["never_downloaded"] is True
        assert by_id["a1"]["stale"] is True
        assert by_id["a2"]["classification"] == "release"
        assert by_id["a2"]["stale"] is False
        assert result["total_assets_scanned"] == 2
        assert result["stale_count"] == 1
        assert result["by_classification"] == {"snapshot": 1, "release": 1}
        # oldest first
        assert result["oldest_first"][0]["asset_id"] == "a1"


@pytest.mark.asyncio
async def test_artifact_age_report_classifies_docker_mutable_tag(nexus_client):
    """Docker 'latest'-style tags are flagged as mutable-tag, not release."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/search/assets").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": "d1",
                            "path": "myapp/latest/manifest.json",
                            "version": "latest",
                            "format": "docker",
                            "blobCreated": "2024-01-01T00:00:00.000Z",
                        }
                    ]
                },
            )
        )

        result = await nexus_client.get_artifact_age_report(
            repository="docker-hosted", format="docker"
        )

        assert result["oldest_first"][0]["classification"] == "mutable-tag"


@pytest.mark.asyncio
async def test_artifact_age_report_no_assets(nexus_client):
    """An empty repository returns a zeroed-out report, not an error."""
    with respx.mock:
        respx.get("http://localhost:8081/service/rest/v1/assets").mock(
            return_value=Response(200, json={"items": []})
        )

        result = await nexus_client.get_artifact_age_report(repository="empty-repo")

        assert result["total_assets_scanned"] == 0
        assert result["stale_count"] == 0
        assert result["oldest_first"] == []
