import httpx

from nexus_mcp.models import RepositoryOwnerInput
from nexus_mcp.nexus_client import NexusClient
from nexus_mcp.repo_info_portal import RepoInfoPortalError, fetch_repository_owner


async def list_repositories(client: NexusClient) -> dict:
    """List all repositories."""
    try:
        repos = await client.list_repositories()
        return {
            "status": "success",
            "data": [
                {
                    "name": repo.name,
                    "format": repo.format,
                    "type": repo.type,
                    "online": repo.online,
                    "url": repo.url,
                }
                for repo in repos
            ],
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


async def get_repository(client: NexusClient, repository_name: str) -> dict:
    """Get a specific repository configuration."""
    try:
        repo = await client.get_repository(repository_name)
        return {
            "status": "success",
            "data": repo,
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


async def get_repository_size(client: NexusClient, repository_name: str) -> dict:
    """Compute total on-disk size (bytes/KiB/MiB/GiB) and asset/component counts.

    Walks the paginated ``/v1/assets`` endpoint for the given repository, so
    runtime scales with the number of assets. See ``_MAX_SIZE_PAGES`` in
    ``nexus_client.py`` if you need to raise the cap.
    """
    if not repository_name:
        return {"status": "error", "error": "repository_name is required"}
    try:
        data = await client.get_repository_size(repository_name)
        return {"status": "success", "data": data}
    except httpx.HTTPError as e:
        return {"status": "error", "error": str(e)}
    except (OSError, ValueError) as e:
        return {"status": "error", "error": str(e)}


async def get_repository_owner(client: NexusClient, input_data: RepositoryOwnerInput) -> dict:
    """Look up a repository's Information Owner (and format/type/access)
    from the Nexus Repo Info portal's data feed — a separate internal
    endpoint, not Nexus's REST API, which has no "owner" concept at all.

    Best-effort: this depends on an internal, undocumented JSON file (not
    a stable API). If it can't be fetched as expected, or the repository
    isn't listed, ``found`` comes back ``False`` rather than a guessed
    answer — check ``source_url`` directly in that case.
    """
    portal_url = client.config.repo_info_portal_url
    if not portal_url:
        return {
            "status": "error",
            "error": (
                "NEXUS_REPO_INFO_URL is not configured for this deployment. "
                "This tool is optional and only works if your org runs a "
                "separate repo-ownership portal -- set NEXUS_REPO_INFO_URL "
                "to its base URL to enable it."
            ),
        }
    try:
        result = await fetch_repository_owner(portal_url, input_data.repository)
        return {"status": "success", "data": result}
    except RepoInfoPortalError as e:
        return {"status": "error", "error": str(e)}
