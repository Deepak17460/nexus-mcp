import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from nexus_mcp.config import Config
from nexus_mcp.http_auth import AuthenticationRequiredError, parse_basic_auth_header
from nexus_mcp.models import (
    ArtifactAgeReportInput,
    CheckArtifactExistsInput,
    ComponentVersionsInput,
    DependencySnippetInput,
    DownloadAssetInput,
    DownloadComponentInput,
    GetDownloadUrlInput,
    LatestArtifactsInput,
    LatestReleaseInput,
    NexusInfoInput,
    RepositoryOwnerInput,
    SearchComponentsInput,
    UploadComponentInput,
)
from nexus_mcp.nexus_client import NexusClient
from nexus_mcp.tools import (
    activity,
    assets,
    components,
    health,
    info,
    repositories,
)

logger = logging.getLogger(__name__)


class NexusServer:
    """MCP Server for Sonatype Nexus OSS."""

    def __init__(self) -> None:
        self.server = Server("nexus-mcp")
        self.config = Config()
        self.client = NexusClient(self.config)

        self._register_tools()

    def _resolve_client(self) -> NexusClient:
        """Pick the NexusClient to use for the current tool call.

        stdio transport (the default, and every deployment before
        MCP_TRANSPORT=http existed): there is no HTTP request in scope, so
        this always returns the server-configured client built from
        NEXUS_USERNAME/PASSWORD/API_TOKEN -- unchanged behavior.

        HTTP transport (a single shared, network-reachable process serving
        many users): requires the current request to carry its own
        'Authorization: Basic <base64(username:password)>' header, and
        builds a fresh, request-scoped NexusClient from it. Never falls
        back to self.client for an HTTP request, even if server-wide
        credentials happen to be configured -- so one caller can never end
        up using another caller's (or the server's own) Nexus identity by
        omission. The returned client is never cached or reused across
        calls, so there is no server-side session state that could leak
        one user's identity into another's request.
        """
        try:
            raw_request = self.server.request_context.request
        except LookupError:
            raw_request = None

        if raw_request is None:
            return self.client

        auth_header = raw_request.headers.get("authorization")
        if not auth_header:
            raise AuthenticationRequiredError(
                "This server is running in hosted mode (MCP_TRANSPORT=http) "
                "-- include an 'Authorization: Basic <base64(username:password)>' "
                "header with your own Nexus credentials on every request."
            )
        username, password = parse_basic_auth_header(auth_header)
        return NexusClient(self.config.with_basic_auth(username, password))

    def _register_tools(self):
        """Register all tools with the MCP server using decorators."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """Return list of available tools."""
            return [
                Tool(
                    name="nexus_health_check",
                    description=(
                        "Check whether Nexus is available for read requests "
                        "and whether the configured credentials are "
                        "actually valid (auth_valid)."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="nexus_check_writable",
                    description=(
                        "Check whether this Nexus node currently accepts writes. "
                        "Use before automated uploads to detect read-only "
                        "maintenance mode or an HA passive node."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="nexus_list_repositories",
                    description="List all repositories (name, format, type, online status)",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="nexus_get_repository",
                    description="Get detailed configuration for a specific repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository_name": {
                                "type": "string",
                                "description": "Name of the repository",
                            }
                        },
                        "required": ["repository_name"],
                    },
                ),
                Tool(
                    name="nexus_search_components",
                    description="Search components with optional filters (repository, format, group, name, version, keyword)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Repository name filter",
                            },
                            "format": {
                                "type": "string",
                                "description": "Component format (maven2, npm, docker, raw, etc.)",
                            },
                            "group": {
                                "type": "string",
                                "description": "Group ID (for Maven components)",
                            },
                            "name": {
                                "type": "string",
                                "description": "Component name",
                            },
                            "version": {
                                "type": "string",
                                "description": "Component version",
                            },
                            "keyword": {
                                "type": "string",
                                "description": "Free-text keyword search",
                            },
                            "continuation_token": {
                                "type": "string",
                                "description": "Token for pagination",
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="nexus_get_component",
                    description="Get detailed information about a component by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "component_id": {
                                "type": "string",
                                "description": "Component ID",
                            }
                        },
                        "required": ["component_id"],
                    },
                ),
                Tool(
                    name="nexus_get_component_versions",
                    description=(
                        "List all distinct versions of a component name in a "
                        "repository, sorted ascending, with the latest version "
                        "surfaced separately. Useful for CI version-bump and "
                        "dependency-resolution workflows."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Repository to search within",
                            },
                            "name": {
                                "type": "string",
                                "description": "Component name to match",
                            },
                            "group": {
                                "type": "string",
                                "description": "Optional group filter (Maven groupId, etc.)",
                            },
                            "format": {
                                "type": "string",
                                "description": "Optional component format filter",
                            },
                        },
                        "required": ["repository", "name"],
                    },
                ),
                Tool(
                    name="nexus_check_artifact_exists",
                    description=(
                        "Check whether a component (optionally at an exact "
                        "version) already exists in a repository. Pass "
                        "version for an exact match; omit it to check "
                        "whether any version of the component exists. "
                        "Handy as a CI pre-flight guard to skip "
                        "re-publishing an artifact that's already there."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Repository to search within",
                            },
                            "name": {
                                "type": "string",
                                "description": "Component name to match",
                            },
                            "version": {
                                "type": "string",
                                "description": (
                                    "Optional exact version to check. Omit "
                                    "to check for any version of this "
                                    "component."
                                ),
                            },
                            "group": {
                                "type": "string",
                                "description": "Optional group filter (Maven groupId, etc.)",
                            },
                            "format": {
                                "type": "string",
                                "description": "Optional component format filter",
                            },
                        },
                        "required": ["repository", "name"],
                    },
                ),
                Tool(
                    name="nexus_get_latest_release",
                    description=(
                        "Find the latest release artifact in a repository. "
                        "Pass name to get the newest version of a specific "
                        "component, or omit it to find the most recently "
                        "published non-snapshot component anywhere in the "
                        "repository. SNAPSHOT-style versions are excluded "
                        "by default."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Repository to search within",
                            },
                            "name": {
                                "type": "string",
                                "description": "Optional component name to restrict the search to",
                            },
                            "group": {
                                "type": "string",
                                "description": "Optional group filter (Maven groupId, etc.)",
                            },
                            "format": {
                                "type": "string",
                                "description": "Optional component format filter",
                            },
                            "include_snapshots": {
                                "type": "boolean",
                                "description": "Include SNAPSHOT-style versions (default false)",
                            },
                        },
                        "required": ["repository"],
                    },
                ),
                Tool(
                    name="nexus_get_asset",
                    description="Get detailed information about an asset by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "asset_id": {
                                "type": "string",
                                "description": "Asset ID",
                            }
                        },
                        "required": ["asset_id"],
                    },
                ),
                Tool(
                    name="nexus_get_download_url",
                    description=(
                        "Resolve one or more direct download URLs without "
                        "fetching content. Pass asset_id for an exact "
                        "single asset, or repository + name (optionally "
                        "version/group/format) to resolve by coordinates. "
                        "Useful for CI scripts that just need a URL to hand "
                        "to curl/wget rather than round-tripping the "
                        "file's bytes through this MCP server — pair with "
                        "nexus_download_asset when you actually need the "
                        "bytes."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "asset_id": {
                                "type": "string",
                                "description": (
                                    "Exact asset ID to resolve. If given, "
                                    "the coordinate fields below are ignored."
                                ),
                            },
                            "repository": {
                                "type": "string",
                                "description": "Repository to search within (required if asset_id is omitted)",
                            },
                            "name": {
                                "type": "string",
                                "description": "Component name to match (required if asset_id is omitted)",
                            },
                            "version": {
                                "type": "string",
                                "description": "Optional exact version filter",
                            },
                            "group": {
                                "type": "string",
                                "description": "Optional group filter (Maven groupId, etc.)",
                            },
                            "format": {
                                "type": "string",
                                "description": "Optional component format filter",
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="nexus_download_asset",
                    description=(
                        "Download a single asset's raw content by its exact ID. "
                        "Returns base64 content bounded by max_size_bytes, or "
                        "writes to save_path when provided. Complements "
                        "nexus_download_component for callers that already "
                        "have a precise asset_id (e.g. from search or "
                        "nexus_get_component) and want the raw bytes directly."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "asset_id": {
                                "type": "string",
                                "description": "Asset ID to download",
                            },
                            "save_path": {
                                "type": "string",
                                "description": (
                                    "Local file path to write the content to. "
                                    "Omit to receive base64 content instead."
                                ),
                            },
                            "max_size_bytes": {
                                "type": "integer",
                                "description": (
                                    "Maximum bytes to download before aborting "
                                    "(default 10 MiB, max 100 MiB)"
                                ),
                                "minimum": 1,
                                "maximum": 104857600,
                            },
                        },
                        "required": ["asset_id"],
                    },
                ),
                Tool(
                    name="nexus_upload_component",
                    description="Upload a component to a hosted repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Target repository name",
                            },
                            "format": {
                                "type": "string",
                                "description": "Component format",
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Local file path to upload",
                            },
                            "file_base64": {
                                "type": "string",
                                "description": "File content as base64 (alternative to file_path)",
                            },
                            "filename": {
                                "type": "string",
                                "description": "Filename in repository",
                            },
                            "group_id": {
                                "type": "string",
                                "description": "Group ID (for Maven)",
                            },
                            "artifact_id": {
                                "type": "string",
                                "description": "Artifact ID (for Maven)",
                            },
                            "version": {
                                "type": "string",
                                "description": "Component version",
                            },
                            "packaging": {
                                "type": "string",
                                "description": "Packaging type (for Maven)",
                            },
                        },
                        "required": ["repository", "format"],
                    },
                ),
                Tool(
                    name="nexus_download_component",
                    description=(
                        "Download a component's assets from a Nexus repository "
                        "by name (optionally filtered by version/group/format). "
                        "Files are saved into save_dir (defaults to CWD)."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Repository to download from",
                            },
                            "name": {
                                "type": "string",
                                "description": "Component name to match",
                            },
                            "version": {
                                "type": "string",
                                "description": "Optional version filter",
                            },
                            "group": {
                                "type": "string",
                                "description": "Optional group filter (Maven groupId, etc.)",
                            },
                            "format": {
                                "type": "string",
                                "description": "Optional component format filter",
                            },
                            "save_dir": {
                                "type": "string",
                                "description": "Local directory to write downloaded files into (defaults to current working directory)",
                            },
                        },
                        "required": ["repository", "name"],
                    },
                ),
                Tool(
                    name="nexus_get_dependency_snippet",
                    description=(
                        "Generate ready-to-paste dependency snippets (Maven "
                        "pom.xml, Gradle, npm, Docker pull/login, pip, or a "
                        "direct download URL) for an artifact so it can be "
                        "added to a codebase. If version/name/format are "
                        "omitted, resolves the latest release in the "
                        "repository first. For Docker, resolves the actual "
                        "pull address — preferring path-based routing "
                        "(docker.pathEnabled, which works behind a reverse "
                        "proxy like nginx that only exposes HTTPS) over a "
                        "dedicated connector host:port when both are "
                        "configured. Also returns the repository's browse URL "
                        "(repository_url) and access_help pointing to where "
                        "to request repo access (Nexus's REST API has no "
                        "concept of 'required role' for a repository). "
                        "Never includes real credentials — only "
                        "environment-variable placeholders."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Repository the artifact lives in",
                            },
                            "name": {
                                "type": "string",
                                "description": "Component/package name (omit to auto-resolve the latest release)",
                            },
                            "group": {
                                "type": "string",
                                "description": "Optional group filter (Maven groupId, etc.)",
                            },
                            "version": {
                                "type": "string",
                                "description": "Version to target (omit to use the latest release)",
                            },
                            "format": {
                                "type": "string",
                                "description": "Component format (maven2, npm, docker, pypi, raw, etc.)",
                            },
                            "build_tool": {
                                "type": "string",
                                "description": (
                                    "Restrict output to one tool's snippets, "
                                    "e.g. 'maven', 'gradle', 'npm', 'pip', "
                                    "'docker'. Omit to get all applicable "
                                    "snippets for the format."
                                ),
                            },
                        },
                        "required": ["repository"],
                    },
                ),
                Tool(
                    name="nexus_get_repository_size",
                    description=(
                        "Return total on-disk size (bytes/KiB/MiB/GiB) plus "
                        "asset and component counts for a repository."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository_name": {
                                "type": "string",
                                "description": "Name of the repository to measure",
                            }
                        },
                        "required": ["repository_name"],
                    },
                ),
                Tool(
                    name="nexus_latest_uploaded_artifacts",
                    description=(
                        "List the most-recently uploaded artifacts, including "
                        "the uploader identity when Nexus records it."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Optional repository to restrict the query to",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of items to return (1-100)",
                                "minimum": 1,
                                "maximum": 100,
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="nexus_latest_downloaded_artifacts",
                    description=(
                        "List the most-recently downloaded artifacts. Nexus "
                        "REST does not expose downloader identity — see the "
                        "downloader_info field for details."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Optional repository to restrict the query to",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of items to return (1-100)",
                                "minimum": 1,
                                "maximum": 100,
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="nexus_get_artifact_age_report",
                    description=(
                        "Report artifact age and download recency for a "
                        "repository (read-only, deletes nothing). For each "
                        "asset, shows upload age, days since last download "
                        "(or never_downloaded), and a classification "
                        "(snapshot, pre-release, mutable-tag for Docker "
                        "latest/dev-style tags, or release). Flags assets as "
                        "'stale' when uploaded and not downloaded within "
                        "stale_after_days — use this to spot old SNAPSHOT, "
                        "pre-release, or Docker artifacts that are candidates "
                        "for cleanup review."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Repository to scan",
                            },
                            "name": {
                                "type": "string",
                                "description": "Optional component name filter",
                            },
                            "group": {
                                "type": "string",
                                "description": "Optional group filter (Maven groupId, etc.)",
                            },
                            "format": {
                                "type": "string",
                                "description": "Optional component format filter",
                            },
                            "stale_after_days": {
                                "type": "integer",
                                "description": "Age/inactivity threshold in days for the 'stale' flag (default 90)",
                                "minimum": 1,
                                "maximum": 3650,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max number of oldest assets to return in detail (default 50, max 200)",
                                "minimum": 1,
                                "maximum": 200,
                            },
                        },
                        "required": ["repository"],
                    },
                ),
                Tool(
                    name="nexus_info",
                    description=(
                        "Look up ServiceNow ticket links (request Nexus "
                        "access, repo creation, admin transfer, settings "
                        "changes, or support), the Nexus repository-info "
                        "portal, and SharePoint documentation. Purely local "
                        "— makes no Nexus REST calls. Pass a free-text query "
                        "(e.g. 'raise a ticket for repo access') to rank the "
                        "most relevant links first, or omit it to list all "
                        "known links."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": (
                                    "Free-text question, e.g. 'how do I get "
                                    "access to a repo' or 'where is the "
                                    "documentation'. Omit to list everything."
                                ),
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="nexus_get_repository_owner",
                    description=(
                        "Look up a repository's Information Owner (plus "
                        "format/type/access) from the Nexus Repo Info "
                        "portal's data feed — a separate internal endpoint, "
                        "not Nexus's REST API (which has no 'owner' concept "
                        "at all). Best-effort: relies on an internal, "
                        "undocumented JSON file, not a stable API — if the "
                        "repository isn't found, 'found' comes back false "
                        "rather than a guessed answer — check 'source_url' "
                        "directly in that case."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repository": {
                                "type": "string",
                                "description": "Exact repository name, e.g. 'maven-releases'",
                            },
                        },
                        "required": ["repository"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Execute a tool and return results."""
            input_data: (
                ArtifactAgeReportInput
                | CheckArtifactExistsInput
                | ComponentVersionsInput
                | DependencySnippetInput
                | DownloadAssetInput
                | DownloadComponentInput
                | GetDownloadUrlInput
                | LatestArtifactsInput
                | LatestReleaseInput
                | NexusInfoInput
                | RepositoryOwnerInput
                | SearchComponentsInput
                | UploadComponentInput
            )
            try:
                # stdio: always the server-configured client (unchanged
                # behavior). HTTP (MCP_TRANSPORT=http): requires a
                # per-request Authorization: Basic header and never falls
                # back to a shared identity -- see _resolve_client().
                client = self._resolve_client()

                if name == "nexus_health_check":
                    result = await health.health_check(client)
                elif name == "nexus_check_writable":
                    result = await health.check_writable(client)
                elif name == "nexus_list_repositories":
                    result = await repositories.list_repositories(client)
                elif name == "nexus_get_repository":
                    result = await repositories.get_repository(
                        client, arguments.get("repository_name", "")
                    )
                elif name == "nexus_search_components":
                    input_data = SearchComponentsInput(**arguments)
                    result = await components.search_components(client, input_data)
                elif name == "nexus_get_component":
                    result = await components.get_component(
                        client, arguments.get("component_id", "")
                    )
                elif name == "nexus_get_component_versions":
                    input_data = ComponentVersionsInput(**arguments)
                    result = await components.get_component_versions(client, input_data)
                elif name == "nexus_check_artifact_exists":
                    input_data = CheckArtifactExistsInput(**arguments)
                    result = await components.check_artifact_exists(client, input_data)
                elif name == "nexus_get_latest_release":
                    input_data = LatestReleaseInput(**arguments)
                    result = await components.get_latest_release(client, input_data)
                elif name == "nexus_get_asset":
                    result = await assets.get_asset(client, arguments.get("asset_id", ""))
                elif name == "nexus_get_download_url":
                    input_data = GetDownloadUrlInput(**arguments)
                    result = await assets.get_download_url(client, input_data)
                elif name == "nexus_download_asset":
                    input_data = DownloadAssetInput(**arguments)
                    result = await assets.download_asset(client, input_data)
                elif name == "nexus_upload_component":
                    input_data = UploadComponentInput(**arguments)
                    result = await components.upload_component(client, input_data)
                elif name == "nexus_download_component":
                    input_data = DownloadComponentInput(**arguments)
                    result = await components.download_component(client, input_data)
                elif name == "nexus_get_dependency_snippet":
                    input_data = DependencySnippetInput(**arguments)
                    result = await components.get_dependency_snippet(client, input_data)
                elif name == "nexus_get_repository_size":
                    result = await repositories.get_repository_size(
                        client, arguments.get("repository_name", "")
                    )
                elif name == "nexus_latest_uploaded_artifacts":
                    input_data = LatestArtifactsInput(**arguments)
                    result = await activity.latest_uploaded_artifacts(client, input_data)
                elif name == "nexus_latest_downloaded_artifacts":
                    input_data = LatestArtifactsInput(**arguments)
                    result = await activity.latest_downloaded_artifacts(client, input_data)
                elif name == "nexus_get_artifact_age_report":
                    input_data = ArtifactAgeReportInput(**arguments)
                    result = await activity.artifact_age_report(client, input_data)
                elif name == "nexus_info":
                    input_data = NexusInfoInput(**arguments)
                    result = await info.nexus_info(input_data)
                elif name == "nexus_get_repository_owner":
                    input_data = RepositoryOwnerInput(**arguments)
                    result = await repositories.get_repository_owner(client, input_data)
                else:
                    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

                return [TextContent(type="text", text=json.dumps(result))]
            except AuthenticationRequiredError as e:
                # Not logged as an exception -- this is an expected, routine
                # outcome in hosted mode (a caller forgot/omitted the
                # header), not a server-side failure.
                return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
            except Exception as e:
                logger.exception("Tool execution error")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Nexus MCP Server running")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )
