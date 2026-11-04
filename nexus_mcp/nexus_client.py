import base64
import pathlib
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from nexus_mcp.config import Config
from nexus_mcp.models import Repository


def _version_sort_key(version: str) -> list[tuple[int, Any]]:
    """Best-effort natural sort key so '1.9.0' sorts before '1.10.0'.

    Numeric dot/dash/underscore-separated segments compare as integers;
    non-numeric segments (e.g. '-rc1', 'SNAPSHOT') fall back to string
    comparison. Not a full semver parser, but good enough for ordering
    typical Maven/npm/raw version strings.
    """
    parts = re.split(r"[.\-+_]", version)
    key: list[tuple[int, Any]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return key


_PRE_RELEASE_PATTERN = re.compile(r"(alpha|beta|-rc\d*|[.-]dev\b|nightly|[.-]pre\b)")
_MUTABLE_DOCKER_TAGS = ("latest", "dev", "nightly", "edge", "main", "master")


def _classify_artifact(asset: dict[str, Any]) -> str:
    """Best-effort classification: 'snapshot', 'pre-release', 'mutable-tag', or 'release'.

    Used for staleness reporting only — never affects what gets returned by
    the read-only search/list tools.
    """
    text = f"{asset.get('version', '')} {asset.get('path', '')}".lower()
    fmt = (asset.get("format") or "").lower()
    if "snapshot" in text:
        return "snapshot"
    if _PRE_RELEASE_PATTERN.search(text):
        return "pre-release"
    if fmt == "docker" and any(tag in text for tag in _MUTABLE_DOCKER_TAGS):
        return "mutable-tag"
    return "release"


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse a Nexus ISO-8601 timestamp string; returns None if absent/invalid."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

# Maximum number of asset pages to walk when sorting client-side (upload/download
# activity queries) or when computing repository sizes. Each page is 50 items on
# a stock Nexus install, so 40 pages ~= 2000 assets. Tune if you need to cover
# larger repositories.
_MAX_ACTIVITY_PAGES = 40
_MAX_SIZE_PAGES = 200


class NexusClient:
    """Async HTTP client for Nexus REST API."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = f"{config.nexus_url}/service/rest/v1"
        self.auth_header = config.get_auth_header()

    async def health_check(self) -> dict[str, Any]:
        """Check whether Nexus can serve read requests, plus authentication.

        ``GET /v1/status`` always returns an *empty* body (per Sonatype's
        Status API) — availability is conveyed only via the status code
        (200 = can serve reads, 503 = unavailable), so this does **not**
        call ``response.json()`` on it (that was the bug: an empty body
        makes ``.json()`` raise ``JSONDecodeError: Expecting value``). It
        also requires no authentication at all, so a second call to
        ``/v1/repositories`` is used to actually confirm the configured
        credentials work. Edition/version aren't reported — Nexus's REST
        API doesn't expose them without an admin-only endpoint
        (``/v1/system-information``), and the ``Server`` response header is
        stripped by many reverse proxies, so it isn't reliable either.
        """
        async with httpx.AsyncClient() as client:
            status_response = await client.get(
                f"{self.config.nexus_url}/service/rest/v1/status",
                headers=self.auth_header,
            )
        available = status_response.status_code == 200

        auth_valid: bool | None = None
        auth_error: str | None = None
        try:
            await self.list_repositories()
            auth_valid = True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                auth_valid = False
                auth_error = (
                    f"Authentication check failed ({e.response.status_code}) "
                    "when listing repositories"
                )
            else:
                auth_error = (
                    "Could not verify authentication (repositories check "
                    f"returned {e.response.status_code})"
                )
        except httpx.HTTPError as e:
            auth_error = f"Could not verify authentication: {e}"

        return {
            "available": available,
            "status_code": status_response.status_code,
            "auth_valid": auth_valid,
            "auth_error": auth_error,
        }

    async def check_writable(self) -> dict[str, Any]:
        """Check whether this Nexus node currently accepts writes.

        Maps to ``GET /v1/status/writable``, which returns 200 when the node
        is writable and a non-2xx status when it is read-only (e.g. an HA
        passive node or a node in maintenance mode). Useful as a pre-flight
        check before an automated upload/promotion pipeline runs.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.config.nexus_url}/service/rest/v1/status/writable",
                headers=self.auth_header,
            )
            return {
                "writable": response.status_code == 200,
                "status_code": response.status_code,
            }

    async def list_repositories(self) -> list[Repository]:
        """List all repositories."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repositories",
                headers=self.auth_header,
            )
            response.raise_for_status()
            data = response.json()
            return [
                Repository(
                    name=repo.get("name", ""),
                    format=repo.get("format", ""),
                    type=repo.get("type", ""),
                    online=repo.get("online", False),
                    url=repo.get("url"),
                )
                for repo in data
            ]

    async def get_repository(self, repository_name: str) -> dict[str, Any]:
        """Get repository configuration."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repositories/{repository_name}",
                headers=self.auth_header,
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    async def search_components(
        self,
        repository: str | None = None,
        format: str | None = None,
        group: str | None = None,
        name: str | None = None,
        version: str | None = None,
        keyword: str | None = None,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        """Search components with filters."""
        params = {}
        if repository:
            params["repository"] = repository
        if format:
            params["format"] = format
        if group:
            params["group"] = group
        if name:
            params["name"] = name
        if version:
            params["version"] = version
        if keyword:
            params["keyword"] = keyword
        if continuation_token:
            params["continuationToken"] = continuation_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/search/assets",
                params=params,
                headers=self.auth_header,
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    async def get_docker_pull_info(
        self, repository: str, repo: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Best-effort resolution of how to pull from a Docker repository.

        The generic ``GET /v1/repositories/{name}`` endpoint (used by
        ``get_repository``) does *not* expose Docker connector settings —
        only the format+type-specific endpoint
        ``GET /v1/repositories/docker/{type}/{name}`` does. This makes that
        second call to check both ways Nexus can expose a Docker registry:

        - ``path_enabled`` (``docker.pathEnabled``): reachable at the *same*
          host/path Nexus itself is served from, e.g.
          ``<nexus-host>/repository/<repo-name>``. This is what actually
          works when Nexus sits behind a reverse proxy (nginx, etc.) that
          only exposes HTTPS on 443 and internally proxies
          repository-scoped paths to the Docker connector — a common setup
          (confirmed: this org's Nexus is exactly this topology).
        - ``connector_host``: a dedicated ``<nexus-host>:<httpPort|
          httpsPort>`` connector. Only reachable if nothing in front of
          Nexus blocks that raw port; a reverse proxy that forwards only
          443 will make this unreachable even though the port is
          configured in Nexus.

        Returns ``None`` if the repository isn't Docker format or the
        lookup fails for any reason. Callers should prefer ``path_enabled``
        over ``connector_host`` when both are present, since it's the form
        that works behind a typical reverse-proxy topology.
        """
        repo = repo or await self.get_repository(repository)
        if (repo.get("format") or "").lower() != "docker":
            return None
        repo_type = repo.get("type")
        if repo_type not in ("hosted", "proxy", "group"):
            return None

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repositories/docker/{repo_type}/{repository}",
                headers=self.auth_header,
            )
            if response.status_code >= 400:
                return None
            data = response.json()

        docker_cfg = data.get("docker") or {}
        port = docker_cfg.get("httpsPort") or docker_cfg.get("httpPort")
        host = urlparse(self.config.nexus_url).hostname

        return {
            "path_enabled": bool(docker_cfg.get("pathEnabled")),
            "connector_host": f"{host}:{port}" if port else None,
        }

    async def get_component(self, component_id: str) -> dict[str, Any]:
        """Get a component by ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/components/{component_id}",
                headers=self.auth_header,
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    async def get_asset(self, asset_id: str) -> dict[str, Any]:
        """Get an asset by ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/assets/{asset_id}",
                headers=self.auth_header,
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    async def download_asset(
        self,
        asset_id: str,
        save_path: str | None = None,
        max_size_bytes: int = 10 * 1024 * 1024,
    ) -> dict[str, Any]:
        """Download a single asset's raw content by its exact ID.

        Writes to ``save_path`` when provided, otherwise buffers and returns
        base64-encoded content. Both modes are bounded by ``max_size_bytes``
        so a single call cannot consume unbounded memory or disk space; the
        partial file is removed if the cap is exceeded while streaming to
        disk.
        """
        asset = await self.get_asset(asset_id)
        download_url = asset.get("downloadUrl")
        if not download_url:
            return {"error": f"Asset '{asset_id}' has no downloadUrl"}

        dest = pathlib.Path(save_path) if save_path else None
        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)

        total = 0
        buffer = bytearray()
        async with httpx.AsyncClient(timeout=60.0) as client, client.stream(
            "GET", download_url, headers=self.auth_header
        ) as stream:
            if stream.status_code >= 400:
                body = await stream.aread()
                return {
                    "error": body.decode(errors="replace"),
                    "status_code": stream.status_code,
                }

            fh = dest.open("wb") if dest else None
            try:
                async for chunk in stream.aiter_bytes():
                    total += len(chunk)
                    if total > max_size_bytes:
                        if fh:
                            fh.close()
                        if dest:
                            dest.unlink(missing_ok=True)
                        return {
                            "error": (
                                f"Asset exceeds max_size_bytes ({max_size_bytes} "
                                "bytes); pass a larger max_size_bytes or use "
                                "save_path to stream a bigger file to disk."
                            )
                        }
                    if fh:
                        fh.write(chunk)
                    else:
                        buffer.extend(chunk)
            finally:
                if fh:
                    fh.close()

        result: dict[str, Any] = {
            "asset_id": asset_id,
            "path": asset.get("path"),
            "size_bytes": total,
            "checksum": asset.get("checksum"),
        }
        if dest:
            result["saved_to"] = str(dest)
        else:
            result["content_base64"] = base64.b64encode(bytes(buffer)).decode("ascii")
        return result

    async def upload_component(
        self,
        repository: str,
        format: str,
        file_path: str | None = None,
        file_base64: str | None = None,
        filename: str | None = None,
        group_id: str | None = None,
        artifact_id: str | None = None,
        version: str | None = None,
        packaging: str | None = None,
    ) -> dict[str, Any]:
        """Upload a component to a repository."""
        # Prepare file content
        if file_path:
            file_content = pathlib.Path(file_path).read_bytes()
            if not filename:
                filename = pathlib.Path(file_path).name
        elif file_base64:
            file_content = base64.b64decode(file_base64)
        else:
            return {"error": "Either file_path or file_base64 is required"}

        # Build form data
        files = {"raw.asset1": (filename, file_content)}
        data = {}

        if format == "maven2" and group_id and artifact_id and version:
            data["maven.groupId"] = group_id
            data["maven.artifactId"] = artifact_id
            data["maven.version"] = version
            data["maven.packaging"] = packaging or "jar"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/components",
                params={"repository": repository},
                files=files,
                data=data if data else None,
                headers=self.auth_header,
            )
            if response.status_code >= 400:
                return {"error": response.text, "status_code": response.status_code}
            return {"message": f"Component uploaded successfully to {repository}"}

    # ------------------------------------------------------------------
    # Download / activity / size tools
    # ------------------------------------------------------------------

    async def _iter_assets(
        self,
        client: httpx.AsyncClient,
        repository: str | None = None,
        max_pages: int = _MAX_ACTIVITY_PAGES,
    ):
        """Yield assets from ``/v1/assets`` (or ``/v1/search/assets`` if no
        repository is given), transparently handling pagination.
        """
        params: dict[str, str] = {}
        if repository:
            url = f"{self.base_url}/assets"
            params["repository"] = repository
        else:
            url = f"{self.base_url}/search/assets"

        for _ in range(max_pages):
            response = await client.get(url, params=params, headers=self.auth_header)
            response.raise_for_status()
            payload = response.json()
            for asset in payload.get("items", []):
                yield asset
            token = payload.get("continuationToken")
            if not token:
                return
            params["continuationToken"] = token

    async def download_component(
        self,
        repository: str,
        name: str,
        version: str | None = None,
        group: str | None = None,
        format: str | None = None,
        save_dir: str | None = None,
    ) -> dict[str, Any]:
        """Download a component's asset(s) by name.

        Searches the given repository for assets whose component ``name`` (and,
        optionally, ``version``/``group``/``format``) match, then streams each
        matching asset to ``save_dir`` (or the current working directory).

        Returns a summary describing what was downloaded.
        """
        target_dir = pathlib.Path(save_dir) if save_dir else pathlib.Path.cwd()
        target_dir.mkdir(parents=True, exist_ok=True)

        params: dict[str, str] = {"repository": repository, "name": name}
        if version:
            params["version"] = version
        if group:
            params["group"] = group
        if format:
            params["format"] = format

        matches: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Search for matching assets (paginated).
            next_params = dict(params)
            for _ in range(_MAX_ACTIVITY_PAGES):
                response = await client.get(
                    f"{self.base_url}/search/assets",
                    params=next_params,
                    headers=self.auth_header,
                )
                response.raise_for_status()
                payload = response.json()
                matches.extend(payload.get("items", []))
                token = payload.get("continuationToken")
                if not token:
                    break
                next_params = dict(params)
                next_params["continuationToken"] = token

            if not matches:
                return {
                    "error": (
                        f"No assets found in repository '{repository}' matching "
                        f"name='{name}'"
                        + (f", version='{version}'" if version else "")
                        + (f", group='{group}'" if group else "")
                    )
                }

            downloaded: list[dict[str, Any]] = []
            for asset in matches:
                download_url = asset.get("downloadUrl")
                if not download_url:
                    continue

                # Use the asset path's basename as the filename so we don't
                # accidentally overwrite unrelated files when many assets share
                # the same component name.
                asset_path = asset.get("path") or name
                filename = pathlib.PurePosixPath(asset_path).name or name
                dest = target_dir / filename

                async with client.stream(
                    "GET", download_url, headers=self.auth_header
                ) as stream:
                    if stream.status_code >= 400:
                        body = await stream.aread()
                        downloaded.append(
                            {
                                "asset_id": asset.get("id"),
                                "path": asset_path,
                                "error": body.decode(errors="replace"),
                                "status_code": stream.status_code,
                            }
                        )
                        continue

                    with dest.open("wb") as fh:
                        async for chunk in stream.aiter_bytes():
                            fh.write(chunk)

                downloaded.append(
                    {
                        "asset_id": asset.get("id"),
                        "path": asset_path,
                        "saved_to": str(dest),
                        "size_bytes": dest.stat().st_size,
                        "checksum": asset.get("checksum"),
                        "uploader": asset.get("uploader"),
                        "last_modified": asset.get("lastModified"),
                    }
                )

        return {
            "repository": repository,
            "name": name,
            "matched_assets": len(matches),
            "downloaded": downloaded,
            "save_dir": str(target_dir),
        }

    async def get_repository_size(self, repository: str) -> dict[str, Any]:
        """Return total on-disk size and asset/component counts for a repo."""
        total_bytes = 0
        asset_count = 0
        component_ids: set[str] = set()
        formats: set[str] = set()

        async with httpx.AsyncClient(timeout=60.0) as client:
            async for asset in self._iter_assets(
                client, repository=repository, max_pages=_MAX_SIZE_PAGES
            ):
                asset_count += 1
                size = asset.get("fileSize")
                if isinstance(size, int):
                    total_bytes += size
                component_id = asset.get("componentId")
                if component_id:
                    component_ids.add(component_id)
                fmt = asset.get("format")
                if fmt:
                    formats.add(fmt)

        return {
            "repository": repository,
            "asset_count": asset_count,
            "component_count": len(component_ids),
            "formats": sorted(formats),
            "total_bytes": total_bytes,
            "total_kib": round(total_bytes / 1024, 2),
            "total_mib": round(total_bytes / (1024 * 1024), 2),
            "total_gib": round(total_bytes / (1024 * 1024 * 1024), 4),
            "note": (
                f"Walked up to {_MAX_SIZE_PAGES} pages of assets. If your repo "
                "is larger, raise _MAX_SIZE_PAGES in nexus_client.py."
            ),
        }

    async def list_latest_uploaded_artifacts(
        self, repository: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return the most-recently uploaded assets sorted by upload time desc.

        Includes the ``uploader`` and ``uploaderIp`` fields when Nexus exposes
        them (Nexus 3.37+). Older Nexus versions may omit these fields.
        """
        collected: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            async for asset in self._iter_assets(
                client, repository=repository, max_pages=_MAX_ACTIVITY_PAGES
            ):
                collected.append(asset)

        # Prefer blobCreated when present, fall back to lastModified.
        def _upload_ts(a: dict[str, Any]) -> str:
            return a.get("blobCreated") or a.get("lastModified") or ""

        collected.sort(key=_upload_ts, reverse=True)
        return [
            {
                "asset_id": a.get("id"),
                "repository": a.get("repository"),
                "format": a.get("format"),
                "path": a.get("path"),
                "download_url": a.get("downloadUrl"),
                "file_size": a.get("fileSize"),
                "uploaded_at": _upload_ts(a),
                "uploader": a.get("uploader"),
                "uploader_ip": a.get("uploaderIp"),
            }
            for a in collected[:limit]
        ]

    async def list_latest_downloaded_artifacts(
        self, repository: str | None = None, limit: int = 10
    ) -> dict[str, Any]:
        """Return the assets with the most-recent ``lastDownloaded`` timestamp.

        Note: Nexus's public REST API exposes ``lastDownloaded`` (timestamp) but
        does *not* expose the identity of the account that performed the
        download. Downloader identity is only available in Nexus audit / access
        logs, which are not addressable through the REST API. The
        ``downloader_info`` field in the response documents this limitation.
        """
        collected: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            async for asset in self._iter_assets(
                client, repository=repository, max_pages=_MAX_ACTIVITY_PAGES
            ):
                if asset.get("lastDownloaded"):
                    collected.append(asset)

        collected.sort(key=lambda a: a.get("lastDownloaded") or "", reverse=True)

        return {
            "downloader_info": (
                "Nexus REST API exposes lastDownloaded timestamps but not the "
                "username/IP of who downloaded an asset. That data lives in the "
                "Nexus audit log (System > Support > Logs > audit.log) which is "
                "not queryable via REST. Original uploader is shown when Nexus "
                "records it."
            ),
            "items": [
                {
                    "asset_id": a.get("id"),
                    "repository": a.get("repository"),
                    "format": a.get("format"),
                    "path": a.get("path"),
                    "download_url": a.get("downloadUrl"),
                    "file_size": a.get("fileSize"),
                    "last_downloaded": a.get("lastDownloaded"),
                    "uploader": a.get("uploader"),
                    "uploader_ip": a.get("uploaderIp"),
                }
                for a in collected[:limit]
            ],
        }

    async def get_component_versions(
        self,
        repository: str,
        name: str,
        group: str | None = None,
        format: str | None = None,
    ) -> dict[str, Any]:
        """List distinct versions of a component name in a repository.

        Uses the component-level ``/v1/search`` endpoint (not
        ``/v1/search/assets``) so each result already carries a top-level
        ``version`` field. Returns versions sorted ascending with the last
        entry surfaced separately as ``latest_version`` for convenience in
        CI/version-bump workflows.
        """
        params: dict[str, str] = {"repository": repository, "name": name}
        if group:
            params["group"] = group
        if format:
            params["format"] = format

        versions: list[str] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=60.0) as client:
            next_params = dict(params)
            for _ in range(_MAX_ACTIVITY_PAGES):
                response = await client.get(
                    f"{self.base_url}/search",
                    params=next_params,
                    headers=self.auth_header,
                )
                response.raise_for_status()
                payload = response.json()
                for component in payload.get("items", []):
                    version = component.get("version")
                    if version and version not in seen:
                        seen.add(version)
                        versions.append(version)
                token = payload.get("continuationToken")
                if not token:
                    break
                next_params = dict(params)
                next_params["continuationToken"] = token

        sorted_versions = sorted(versions, key=_version_sort_key)
        return {
            "repository": repository,
            "name": name,
            "group": group,
            "format": format,
            "version_count": len(sorted_versions),
            "versions": sorted_versions,
            "latest_version": sorted_versions[-1] if sorted_versions else None,
        }

    async def get_latest_release(
        self,
        repository: str,
        name: str | None = None,
        group: str | None = None,
        format: str | None = None,
        include_snapshots: bool = False,
    ) -> dict[str, Any]:
        """Find the latest release component in a repository.

        If ``name`` is given, returns the highest version of that specific
        component (excluding SNAPSHOT-style versions unless
        ``include_snapshots=True``). If ``name`` is omitted, scans the
        repository's components via ``/v1/search`` and returns the most
        recently published non-snapshot component, using each component's
        newest asset timestamp as the recency signal. Walks up to
        ``_MAX_ACTIVITY_PAGES`` pages of results.
        """
        params: dict[str, str] = {"repository": repository}
        if name:
            params["name"] = name
        if group:
            params["group"] = group
        if format:
            params["format"] = format

        def _is_snapshot(version: str) -> bool:
            return "snapshot" in version.lower()

        def _component_timestamp(component: dict[str, Any]) -> str:
            timestamps = [
                a.get("blobCreated") or a.get("lastModified") or ""
                for a in component.get("assets", [])
            ]
            return max(timestamps, default="")

        candidates: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            next_params = dict(params)
            for _ in range(_MAX_ACTIVITY_PAGES):
                response = await client.get(
                    f"{self.base_url}/search",
                    params=next_params,
                    headers=self.auth_header,
                )
                response.raise_for_status()
                payload = response.json()
                for component in payload.get("items", []):
                    version = component.get("version") or ""
                    if not include_snapshots and _is_snapshot(version):
                        continue
                    candidates.append(component)
                token = payload.get("continuationToken")
                if not token:
                    break
                next_params = dict(params)
                next_params["continuationToken"] = token

        if not candidates:
            return {
                "error": (
                    f"No release components found in repository '{repository}'"
                    + (f" matching name='{name}'" if name else "")
                    + ("" if include_snapshots else " (snapshots excluded)")
                )
            }

        best = (
            max(candidates, key=lambda c: _version_sort_key(c.get("version") or ""))
            if name
            else max(candidates, key=_component_timestamp)
        )

        return {
            "repository": repository,
            "group": best.get("group"),
            "name": best.get("name"),
            "version": best.get("version"),
            "format": best.get("format"),
            "component_id": best.get("id"),
            "candidates_considered": len(candidates),
            "assets": [
                {
                    "asset_id": a.get("id"),
                    "path": a.get("path"),
                    "download_url": a.get("downloadUrl"),
                    "file_size": a.get("fileSize"),
                    "checksum": a.get("checksum"),
                }
                for a in best.get("assets", [])
            ],
        }

    async def check_artifact_exists(
        self,
        repository: str,
        name: str,
        version: str | None = None,
        group: str | None = None,
        format: str | None = None,
    ) -> dict[str, Any]:
        """Check whether a component (optionally at an exact version) exists.

        Thin existence check on top of the component-level ``/v1/search``
        endpoint — useful as a CI pre-flight guard to skip re-publishing an
        artifact that's already there. Pass ``version`` for an exact match;
        omit it to check whether *any* version of the component exists.
        """
        params: dict[str, str] = {"repository": repository, "name": name}
        if version:
            params["version"] = version
        if group:
            params["group"] = group
        if format:
            params["format"] = format

        matches: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            next_params = dict(params)
            for _ in range(_MAX_ACTIVITY_PAGES):
                response = await client.get(
                    f"{self.base_url}/search",
                    params=next_params,
                    headers=self.auth_header,
                )
                response.raise_for_status()
                payload = response.json()
                matches.extend(payload.get("items", []))
                token = payload.get("continuationToken")
                if not token:
                    break
                next_params = dict(params)
                next_params["continuationToken"] = token

        return {
            "exists": bool(matches),
            "repository": repository,
            "name": name,
            "version": version,
            "group": group,
            "format": format,
            "match_count": len(matches),
            "matches": [
                {
                    "component_id": c.get("id"),
                    "group": c.get("group"),
                    "name": c.get("name"),
                    "version": c.get("version"),
                    "format": c.get("format"),
                    "assets": [
                        {
                            "asset_id": a.get("id"),
                            "path": a.get("path"),
                            "download_url": a.get("downloadUrl"),
                            "file_size": a.get("fileSize"),
                        }
                        for a in c.get("assets", [])
                    ],
                }
                for c in matches
            ],
        }

    async def get_download_url(
        self,
        asset_id: str | None = None,
        repository: str | None = None,
        name: str | None = None,
        version: str | None = None,
        group: str | None = None,
        format: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one or more direct download URLs without fetching content.

        Pass ``asset_id`` for an exact single asset, or ``repository`` +
        ``name`` (optionally ``version``/``group``/``format``) to resolve by
        coordinates. Useful for CI scripts that just need a URL to hand to
        curl/wget rather than round-tripping the file's bytes through this
        MCP server.
        """
        if asset_id:
            asset = await self.get_asset(asset_id)
            download_url = asset.get("downloadUrl")
            if not download_url:
                return {"error": f"Asset '{asset_id}' has no downloadUrl"}
            return {
                "match_count": 1,
                "matches": [
                    {
                        "asset_id": asset_id,
                        "path": asset.get("path"),
                        "download_url": download_url,
                        "file_size": asset.get("fileSize"),
                        "checksum": asset.get("checksum"),
                    }
                ],
            }

        if not (repository and name):
            return {"error": "Provide either asset_id, or repository and name"}

        params: dict[str, str] = {"repository": repository, "name": name}
        if version:
            params["version"] = version
        if group:
            params["group"] = group
        if format:
            params["format"] = format

        matches: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            next_params = dict(params)
            for _ in range(_MAX_ACTIVITY_PAGES):
                response = await client.get(
                    f"{self.base_url}/search/assets",
                    params=next_params,
                    headers=self.auth_header,
                )
                response.raise_for_status()
                payload = response.json()
                matches.extend(payload.get("items", []))
                token = payload.get("continuationToken")
                if not token:
                    break
                next_params = dict(params)
                next_params["continuationToken"] = token

        if not matches:
            return {
                "error": (
                    f"No assets found in repository '{repository}' matching "
                    f"name='{name}'"
                    + (f", version='{version}'" if version else "")
                    + (f", group='{group}'" if group else "")
                )
            }

        return {
            "match_count": len(matches),
            "matches": [
                {
                    "asset_id": a.get("id"),
                    "path": a.get("path"),
                    "download_url": a.get("downloadUrl"),
                    "file_size": a.get("fileSize"),
                    "checksum": a.get("checksum"),
                }
                for a in matches
            ],
        }

    async def get_artifact_age_report(
        self,
        repository: str,
        name: str | None = None,
        group: str | None = None,
        format: str | None = None,
        stale_after_days: int = 90,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Report artifact age and download recency for a repository.

        Read-only staleness report — never deletes anything. Surfaces, per
        asset: upload age, days since last download (or ``never_downloaded``
        if it has none), and a best-effort classification (``snapshot``,
        ``pre-release``, ``mutable-tag`` for Docker's ``latest``/``dev``-style
        tags, or ``release``). An asset is flagged ``stale`` when it was
        uploaded at least ``stale_after_days`` ago *and* either was never
        downloaded or wasn't downloaded within that same window — useful for
        spotting old SNAPSHOT/pre-release/Docker artifacts that are
        candidates for cleanup review. Walks up to ``_MAX_SIZE_PAGES`` pages
        of assets.
        """
        params: dict[str, str] = {"repository": repository}
        if name:
            params["name"] = name
        if group:
            params["group"] = group
        if format:
            params["format"] = format

        # Only /search/assets supports name/group/format filters; /assets is
        # repository-scoped only but is the canonical way to list everything
        # in a repository when no extra filters are given.
        use_search = bool(name or group or format)
        url = f"{self.base_url}/search/assets" if use_search else f"{self.base_url}/assets"

        now = datetime.now(UTC)
        items: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            next_params = dict(params)
            for _ in range(_MAX_SIZE_PAGES):
                response = await client.get(
                    url, params=next_params, headers=self.auth_header
                )
                response.raise_for_status()
                payload = response.json()
                for asset in payload.get("items", []):
                    uploaded_at = _parse_timestamp(
                        asset.get("blobCreated") or asset.get("lastModified")
                    )
                    last_downloaded = _parse_timestamp(asset.get("lastDownloaded"))
                    age_days = (now - uploaded_at).days if uploaded_at else None
                    days_since_download = (
                        (now - last_downloaded).days if last_downloaded else None
                    )
                    stale = bool(
                        age_days is not None
                        and age_days >= stale_after_days
                        and (
                            days_since_download is None
                            or days_since_download >= stale_after_days
                        )
                    )
                    items.append(
                        {
                            "asset_id": asset.get("id"),
                            "path": asset.get("path"),
                            "format": asset.get("format"),
                            "classification": _classify_artifact(asset),
                            "uploaded_at": asset.get("blobCreated")
                            or asset.get("lastModified"),
                            "age_days": age_days,
                            "last_downloaded": asset.get("lastDownloaded"),
                            "days_since_last_download": days_since_download,
                            "never_downloaded": last_downloaded is None,
                            "stale": stale,
                            "file_size": asset.get("fileSize"),
                        }
                    )
                token = payload.get("continuationToken")
                if not token:
                    break
                next_params = dict(params)
                next_params["continuationToken"] = token

        items.sort(key=lambda i: i["uploaded_at"] or "")  # oldest first

        by_classification: dict[str, int] = {}
        for item in items:
            key = item["classification"]
            by_classification[key] = by_classification.get(key, 0) + 1

        stale_count = sum(1 for item in items if item["stale"])

        return {
            "repository": repository,
            "name": name,
            "group": group,
            "format": format,
            "stale_after_days": stale_after_days,
            "total_assets_scanned": len(items),
            "by_classification": by_classification,
            "stale_count": stale_count,
            "oldest_first": items[:limit],
            "note": (
                f"Scanned up to {_MAX_SIZE_PAGES} pages of assets. 'stale' means "
                f"uploaded >= {stale_after_days} days ago AND (never downloaded "
                f"or not downloaded in >= {stale_after_days} days). Read-only "
                "report — pair with nexus_get_latest_release / "
                "nexus_get_component_versions before deciding what to remove."
            ),
        }
