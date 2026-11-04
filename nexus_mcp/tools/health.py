import httpx

from nexus_mcp.nexus_client import NexusClient


async def health_check(client: NexusClient) -> dict:
    """Health check tool - returns Nexus availability, version, and auth status."""
    try:
        data = await client.health_check()
        return {
            "status": "success",
            "data": data,
        }
    except httpx.HTTPError as e:
        return {
            "status": "error",
            "error": str(e),
            "auth_valid": None,
        }
    except (OSError, ValueError) as e:
        return {
            "status": "error",
            "error": str(e),
            "auth_valid": None,
        }


async def check_writable(client: NexusClient) -> dict:
    """Check whether this Nexus node currently accepts writes.

    Useful as a pre-flight guard before an automated upload/promotion
    pipeline runs, e.g. to detect an HA passive node or read-only maintenance
    mode before attempting `nexus_upload_component`.
    """
    try:
        data = await client.check_writable()
        return {
            "status": "success",
            "data": data,
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
