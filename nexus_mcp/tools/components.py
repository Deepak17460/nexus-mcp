from typing import Any

import httpx

from nexus_mcp.models import (
    CheckArtifactExistsInput,
    ComponentVersionsInput,
    DependencySnippetInput,
    DownloadComponentInput,
    LatestReleaseInput,
    SearchComponentsInput,
    UploadComponentInput,
)
from nexus_mcp.nexus_client import NexusClient


async def search_components(
    client: NexusClient, input_data: SearchComponentsInput
) -> dict:
    """Search components with optional filters."""
    try:
        result = await client.search_components(
            repository=input_data.repository,
            format=input_data.format,
            group=input_data.group,
            name=input_data.name,
            version=input_data.version,
            keyword=input_data.keyword,
            continuation_token=input_data.continuation_token,
        )
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


async def get_component(client: NexusClient, component_id: str) -> dict:
    """Get a component by ID."""
    try:
        component = await client.get_component(component_id)
        return {
            "status": "success",
            "data": component,
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


async def upload_component(
    client: NexusClient, input_data: UploadComponentInput
) -> dict:
    """Upload a component to a repository."""
    try:
        result = await client.upload_component(
            repository=input_data.repository,
            format=input_data.format,
            file_path=input_data.file_path,
            file_base64=input_data.file_base64,
            filename=input_data.filename,
            group_id=input_data.group_id,
            artifact_id=input_data.artifact_id,
            version=input_data.version,
            packaging=input_data.packaging,
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
    except (httpx.HTTPError, OSError, ValueError) as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def download_component(
    client: NexusClient, input_data: DownloadComponentInput
) -> dict:
    """Download a component (all matching assets) from a Nexus repository."""
    try:
        result = await client.download_component(
            repository=input_data.repository,
            name=input_data.name,
            version=input_data.version,
            group=input_data.group,
            format=input_data.format,
            save_dir=input_data.save_dir,
        )
        if "error" in result:
            return {"status": "error", "error": result["error"]}
        return {"status": "success", "data": result}
    except (httpx.HTTPError, OSError, ValueError) as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def get_component_versions(
    client: NexusClient, input_data: ComponentVersionsInput
) -> dict:
    """List all distinct versions of a component name, with latest surfaced."""
    try:
        result = await client.get_component_versions(
            repository=input_data.repository,
            name=input_data.name,
            group=input_data.group,
            format=input_data.format,
        )
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


async def get_latest_release(client: NexusClient, input_data: LatestReleaseInput) -> dict:
    """Find the latest release component in a repository (optionally by name)."""
    try:
        result = await client.get_latest_release(
            repository=input_data.repository,
            name=input_data.name,
            group=input_data.group,
            format=input_data.format,
            include_snapshots=input_data.include_snapshots,
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


async def check_artifact_exists(
    client: NexusClient, input_data: CheckArtifactExistsInput
) -> dict:
    """Check whether a component (optionally at an exact version) exists.

    CI pre-flight guard: skip re-publishing an artifact that's already
    there. Pass ``version`` for an exact match; omit it to check whether
    *any* version of the component exists.
    """
    try:
        result = await client.check_artifact_exists(
            repository=input_data.repository,
            name=input_data.name,
            version=input_data.version,
            group=input_data.group,
            format=input_data.format,
        )
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


def _build_access_help(repo_info_portal_url: str) -> str:
    """Build the access_help hint for get_dependency_snippet.

    Points at nexus_get_repository_owner / the configured
    NEXUS_REPO_INFO_URL rather than any hardcoded org-specific URL, since
    that portal (if any) differs per deployment.
    """
    portal_hint = (
        f"({repo_info_portal_url}) "
        if repo_info_portal_url
        else "(requires NEXUS_REPO_INFO_URL to be configured) "
    )
    return (
        "Nexus's REST API doesn't expose which role is required to access "
        "a repository — that mapping is tracked outside Nexus. Use the "
        "nexus_info tool for your org's access-request process, or "
        f"nexus_get_repository_owner {portal_hint}"
        "for this repository's current approver/role."
    )


def _build_dependency_snippets(
    format: str,
    repository: str,
    nexus_url: str,
    group: str | None,
    name: str,
    version: str,
    download_url: str | None,
    docker_pull_info: dict[str, Any] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Build ready-to-paste dependency snippets for common build tools.

    Pure string templating — no network calls. Never embeds real
    credentials; always points callers at an environment variable or
    credential store instead.
    """
    repo_url = f"{nexus_url}/repository/{repository}"
    fmt = (format or "").lower()
    snippets: dict[str, str] = {}
    notes: list[str] = []

    if fmt == "maven2":
        group_id = group or "GROUP_ID"
        snippets["maven_dependency"] = (
            "<dependency>\n"
            f"  <groupId>{group_id}</groupId>\n"
            f"  <artifactId>{name}</artifactId>\n"
            f"  <version>{version}</version>\n"
            "</dependency>"
        )
        snippets["maven_repository"] = (
            "<repository>\n"
            f"  <id>{repository}</id>\n"
            f"  <url>{repo_url}</url>\n"
            "</repository>"
        )
        snippets["gradle_dependency"] = f'implementation "{group_id}:{name}:{version}"'
        snippets["gradle_repository"] = f'maven {{\n    url "{repo_url}"\n}}'
        notes.append(
            "Add credentials via ~/.m2/settings.xml <server> (Maven) or "
            "~/.gradle/gradle.properties (Gradle) — never hardcode them in "
            "pom.xml/build.gradle."
        )
    elif fmt == "npm":
        registry_url = f"{repo_url}/"
        snippets["npm_install"] = f"npm install {name}@{version} --registry={registry_url}"
        snippets["npm_registry"] = f"registry={registry_url}"
        snippets["npm_package_json"] = f'"{name}": "{version}"'
        notes.append(
            f"Authenticate with `npm login --registry={registry_url}` or set "
            "an _authToken in .npmrc from an environment variable; never "
            "commit tokens."
        )
    elif fmt == "docker":
        docker_info = docker_pull_info or {}
        connector_host = docker_info.get("connector_host")
        path_host = repo_url.split("://", 1)[-1]  # e.g. "nexus-host/repository/docker-hosted"

        if docker_info.get("path_enabled"):
            snippets["docker_pull"] = f"docker pull {path_host}/{name}:{version}"
            snippets["docker_login"] = f"docker login {path_host.split('/', 1)[0]}"
            notes.append(
                "Uses Nexus's path-based Docker routing (docker.pathEnabled) "
                "— the same host/path Nexus itself is served from. This is "
                "the form that works behind a reverse proxy (e.g. nginx) "
                "that only exposes HTTPS and internally proxies this path "
                "to the Docker connector."
            )
            if connector_host:
                notes.append(
                    f"A dedicated connector is also configured at "
                    f"{connector_host}, but prefer the path-based pull "
                    "above unless you've confirmed that raw port is "
                    "reachable through any reverse proxy in front of Nexus."
                )
        elif connector_host:
            snippets["docker_pull"] = f"docker pull {connector_host}/{name}:{version}"
            snippets["docker_login"] = f"docker login {connector_host}"
            notes.append(
                "Resolved via this repository's dedicated Docker connector "
                "port (docker.httpPort/httpsPort). If Nexus sits behind a "
                "reverse proxy that only exposes HTTPS/443 externally, "
                "this raw port may not actually be reachable — confirm "
                "with your Nexus administrator, or check whether "
                "path-based routing (pathEnabled) is configured instead."
            )
        else:
            snippets["docker_pull"] = f"docker pull <docker-connector-host>/{name}:{version}"
            notes.append(
                "This repository has neither path-based routing nor an "
                "HTTP/HTTPS connector port configured (or it couldn't be "
                "resolved) — ask your Nexus administrator for the actual "
                "pull address."
            )
    elif fmt == "pypi":
        snippets["pip_install"] = f"pip install {name}=={version} --index-url {repo_url}/simple"
        notes.append("Pass credentials via a pip config file or env vars, not on the command line.")
    else:
        notes.append(
            f"No dedicated build-tool template for format '{format or 'unknown'}'; "
            "use direct_url/curl_download instead."
        )

    if download_url:
        snippets["direct_url"] = download_url
        snippets["curl_download"] = (
            f'curl -L -H "Authorization: Bearer $NEXUS_TOKEN" -o {name} "{download_url}"'
        )

    return snippets, notes


async def get_dependency_snippet(
    client: NexusClient, input_data: DependencySnippetInput
) -> dict:
    """Resolve an artifact (latest release if version omitted) and return
    ready-to-paste dependency snippets for common build tools."""
    try:
        group = input_data.group
        name = input_data.name
        version = input_data.version
        format_ = input_data.format
        download_url: str | None = None

        if not name or not version or not format_:
            resolved = await client.get_latest_release(
                repository=input_data.repository,
                name=name,
                group=group,
                format=format_,
            )
            if "error" in resolved:
                return {"status": "error", "error": resolved["error"]}
            group = group or resolved.get("group")
            name = name or resolved.get("name")
            version = version or resolved.get("version")
            format_ = format_ or resolved.get("format")
            assets: list[dict[str, Any]] = resolved.get("assets", [])
            if assets:
                download_url = assets[0].get("download_url")

        if not name or not version:
            return {
                "status": "error",
                "error": "Could not resolve a component name/version to build a snippet for.",
            }

        repo_info = await client.get_repository(input_data.repository)
        repository_url = repo_info.get("url")

        docker_pull_info: dict[str, Any] | None = None
        if (format_ or "").lower() == "docker":
            docker_pull_info = await client.get_docker_pull_info(
                input_data.repository, repo=repo_info
            )

        snippets, notes = _build_dependency_snippets(
            format=format_ or "",
            repository=input_data.repository,
            nexus_url=client.config.nexus_url,
            group=group,
            name=name,
            version=version,
            download_url=download_url,
            docker_pull_info=docker_pull_info,
        )

        if input_data.build_tool:
            prefix = input_data.build_tool.lower()
            filtered = {
                k: v
                for k, v in snippets.items()
                if k.startswith(prefix) or k in ("direct_url", "curl_download")
            }
            if filtered:
                snippets = filtered
            else:
                notes.append(
                    f"No snippet matched build_tool='{input_data.build_tool}'; "
                    "showing all available snippets for this format instead."
                )

        return {
            "status": "success",
            "data": {
                "repository": input_data.repository,
                "repository_url": repository_url,
                "group": group,
                "name": name,
                "version": version,
                "format": format_,
                "snippets": snippets,
                "notes": notes,
                "access_help": _build_access_help(client.config.repo_info_portal_url),
            },
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
