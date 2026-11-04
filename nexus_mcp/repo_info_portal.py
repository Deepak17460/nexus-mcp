"""Client for an org-specific "Nexus Repo Info" portal's repository-owner
data.

This is an optional, org-specific feature: some orgs run a separate
internal page (configured via ``NEXUS_REPO_INFO_URL``, no default) that
lists every repository's owner. It is not part of Nexus's REST API. Nexus's own
REST API has no concept of "owner" at all (there's no such field on
``GET /v1/repositories/{name}`` or any other endpoint), so this portal is
the only source for that information.

Confirmed via the portal page's own source (view-source, not the rendered
DOM): the ``<table>`` it displays starts with an *empty* ``<tbody>`` — all
rows are populated client-side by JavaScript that does
``fetch('repositories.json')`` (a URL relative to the portal page) and
renders one row per JSON object, reading these fields: ``repository_name``,
``repository_format``, ``repo_type``, ``access_type``, ``info_owner``. So
fetching the portal page's HTML directly (as an earlier version of this
module did) can never see real data — there is none in that response. This
module instead fetches ``repositories.json`` directly, exactly like the
page's own JavaScript does.

Deliberately kept out of ``nexus_client.py``: that module owns Nexus's REST
API specifically (see the nexus-mcp-architecture skill), and this hits a
completely different host/path with a different (and unstable) response
shape that isn't part of any Nexus API contract.

Because this depends on an internal, undocumented JSON file (not a stable
API), every result is best-effort: if it can't be fetched/parsed as
expected, or the repository isn't listed, this returns a clear "not found"
result rather than guessing or fabricating an owner.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import httpx

_TIMEOUT = 15.0
_DATA_FILE = "repositories.json"


class RepoInfoPortalError(Exception):
    """Raised when the portal's data file can't be fetched/parsed at all
    (network/HTTP error, or an unexpected non-list response shape)."""


async def fetch_repository_owner(portal_url: str, repository: str) -> dict[str, Any]:
    """Fetch the Repo Info portal's ``repositories.json`` and return one
    repository's entry.

    Returns a dict with ``found`` (bool), ``repository``, and
    ``source_url``. When found, also includes ``format``, ``type``,
    ``access`` (as published on the portal, e.g. "Public"/"Private"), and
    ``owners`` (list[str] parsed from ``info_owner``, which may list more
    than one person, comma-separated).

    Raises ``RepoInfoPortalError`` if the data file can't be retrieved or
    isn't a JSON list.
    """
    # urljoin treats a URL with no trailing slash as a "file", which would
    # drop the last path segment (e.g. .../nexus-repo-info -> .../repositories.json
    # instead of .../nexus-repo-info/repositories.json) — normalize first so
    # this resolves the same way the portal page's own relative fetch() does.
    base = portal_url if portal_url.endswith("/") else portal_url + "/"
    data_url = urljoin(base, _DATA_FILE)

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        try:
            response = await client.get(data_url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise RepoInfoPortalError(
                f"Could not fetch the Repo Info portal's repository data: {e}"
            ) from e
        except ValueError as e:
            raise RepoInfoPortalError(
                f"Repo Info portal's repository data wasn't valid JSON: {e}"
            ) from e

    result = _find_repository(data, repository)
    result["source_url"] = data_url
    return result


def _find_repository(data: Any, repository: str) -> dict[str, Any]:
    if not isinstance(data, list):
        return {
            "found": False,
            "repository": repository,
            "parse_note": (
                "The portal's repository data wasn't a JSON list as "
                "expected — its format may have changed."
            ),
        }

    target = repository.strip().lower()
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("repository_name") or "").strip()
        if name.lower() != target:
            continue

        owner_text = str(entry.get("info_owner") or "")
        owners = [o.strip() for o in re.split(r"[,;]", owner_text) if o.strip()]

        return {
            "found": True,
            "repository": repository,
            "format": entry.get("repository_format") or None,
            "type": entry.get("repo_type") or None,
            "access": entry.get("access_type") or None,
            "owners": owners,
        }

    return {"found": False, "repository": repository}
