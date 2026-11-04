"""Tools that expose asset activity (latest uploads/downloads/age)."""

import httpx

from nexus_mcp.models import (
    ArtifactAgeReportInput,
    LatestArtifactsInput,
)
from nexus_mcp.nexus_client import NexusClient


async def latest_uploaded_artifacts(
    client: NexusClient, input_data: LatestArtifactsInput
) -> dict:
    """Return the most-recently uploaded artifacts (with uploader when known)."""
    try:
        items = await client.list_latest_uploaded_artifacts(
            repository=input_data.repository,
            limit=input_data.limit,
        )
        return {
            "status": "success",
            "data": {
                "repository": input_data.repository,
                "limit": input_data.limit,
                "count": len(items),
                "items": items,
            },
        }
    except httpx.HTTPError as e:
        return {"status": "error", "error": str(e)}
    except (OSError, ValueError) as e:
        return {"status": "error", "error": str(e)}


async def latest_downloaded_artifacts(
    client: NexusClient, input_data: LatestArtifactsInput
) -> dict:
    """Return the most-recently downloaded artifacts.

    Note: Nexus REST does not expose downloader identity — see
    ``downloader_info`` in the response for details.
    """
    try:
        payload = await client.list_latest_downloaded_artifacts(
            repository=input_data.repository,
            limit=input_data.limit,
        )
        return {
            "status": "success",
            "data": {
                "repository": input_data.repository,
                "limit": input_data.limit,
                "count": len(payload.get("items", [])),
                **payload,
            },
        }
    except httpx.HTTPError as e:
        return {"status": "error", "error": str(e)}
    except (OSError, ValueError) as e:
        return {"status": "error", "error": str(e)}


async def artifact_age_report(
    client: NexusClient, input_data: ArtifactAgeReportInput
) -> dict:
    """Report artifact age/staleness so old snapshot/pre-release/Docker
    artifacts that are candidates for cleanup review can be spotted."""
    try:
        result = await client.get_artifact_age_report(
            repository=input_data.repository,
            name=input_data.name,
            group=input_data.group,
            format=input_data.format,
            stale_after_days=input_data.stale_after_days,
            limit=input_data.limit,
        )
        return {"status": "success", "data": result}
    except httpx.HTTPError as e:
        return {"status": "error", "error": str(e)}
    except (OSError, ValueError) as e:
        return {"status": "error", "error": str(e)}
