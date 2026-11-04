import httpx

from nexus_mcp.models import DownloadAssetInput, GetDownloadUrlInput
from nexus_mcp.nexus_client import NexusClient


async def get_asset(client: NexusClient, asset_id: str) -> dict:
    """Get an asset by ID."""
    try:
        asset = await client.get_asset(asset_id)
        return {
            "status": "success",
            "data": asset,
        }
    except httpx.HTTPError as e:
        return {
            "status": "error",
            "error": str(e),
        }
    except (OSError, ValueError) as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def get_download_url(client: NexusClient, input_data: GetDownloadUrlInput) -> dict:
    """Resolve one or more direct download URLs without fetching content.

    Pass ``asset_id`` for an exact single asset, or ``repository`` + ``name``
    (optionally ``version``/``group``/``format``) to resolve by coordinates.
    Useful for CI scripts that just need a URL to hand to curl/wget rather
    than round-tripping the file's bytes through this MCP server.
    """
    try:
        result = await client.get_download_url(
            asset_id=input_data.asset_id,
            repository=input_data.repository,
            name=input_data.name,
            version=input_data.version,
            group=input_data.group,
            format=input_data.format,
        )
        if "error" in result:
            return {"status": "error", "error": result["error"]}
        return {
            "status": "success",
            "data": result,
        }
    except httpx.HTTPError as e:
        return {
            "status": "error",
            "error": str(e),
        }
    except (OSError, ValueError) as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def download_asset(client: NexusClient, input_data: DownloadAssetInput) -> dict:
    """Download a single asset's raw content by its exact ID."""
    try:
        result = await client.download_asset(
            input_data.asset_id,
            save_path=input_data.save_path,
            max_size_bytes=input_data.max_size_bytes,
        )
        if "error" in result:
            return {
                "status": "error",
                "error": result["error"],
                "status_code": result.get("status_code"),
            }
        return {
            "status": "success",
            "data": result,
        }
    except httpx.HTTPError as e:
        return {
            "status": "error",
            "error": str(e),
        }
    except (OSError, ValueError) as e:
        return {
            "status": "error",
            "error": str(e),
        }
