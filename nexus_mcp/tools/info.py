"""Local knowledge-base lookup: links to your org's own access-request
process, repo-ownership portal, and documentation/wiki.

Purely local — makes no Nexus REST calls, needs no credentials. Reads
Markdown files from ``nexus/kb/`` (see ``nexus/README.md``) so non-engineers
can add/update links without touching Python code. Falls back to a small
embedded copy if that directory can't be found (e.g. an unusual install
layout), so this tool never hard-fails.
"""

import re
from pathlib import Path
from typing import Any

from nexus_mcp.models import NexusInfoInput

# Keep in sync with nexus/kb/*.md — used only if that directory is missing.
# These are intentionally generic placeholders: this whole tool exists so
# *your* org can drop its own Markdown files into nexus/kb/ (ServiceNow
# catalog links, an internal wiki, a repo-ownership portal, etc.) without
# touching any Python code. Replace these entries/files with your own.
_FALLBACK_ENTRIES: list[dict[str, Any]] = [
    {
        "id": "access-request-example",
        "title": "Example - Request Nexus Access (replace with your org's link)",
        "url": "https://example.com/request-nexus-access",
        "category": "servicenow",
        "keywords": [
            "access", "permission", "role", "ci user", "request access",
            "raise a ticket", "raise ticket", "repository creation",
            "transfer admin", "repository settings", "support", "catalog",
        ],
        "body": (
            "Placeholder for your org's access-request process (e.g. a "
            "ServiceNow catalog item, Jira Service Desk form, or ticketing "
            "system) covering: repository access requests, repository "
            "creation requests, ownership transfer, and general support. "
            "Edit nexus/kb/*.md (or this fallback) to point at your own."
        ),
    },
    {
        "id": "repo-info-portal-example",
        "title": "Example - Repository Info / Ownership Portal",
        "url": "https://example.com/nexus-repo-info/",
        "category": "portal",
        "keywords": [
            "repo info", "repository list", "browse repositories",
            "repo owner", "find repository", "approver",
        ],
        "body": (
            "Placeholder for an org-specific page listing repository "
            "owners/approvers (see nexus_get_repository_owner and the "
            "NEXUS_REPO_INFO_URL env var, which this is unrelated to by "
            "default — set both to point at your own portal)."
        ),
    },
    {
        "id": "documentation-example",
        "title": "Example - Internal Documentation / Wiki",
        "url": "https://example.com/nexus-docs",
        "category": "documentation",
        "keywords": ["documentation", "guide", "wiki", "policy", "how to"],
        "body": "Placeholder for your org's internal Nexus documentation/wiki.",
    },
]


def _find_kb_dir() -> Path | None:
    """Locate ``nexus/kb`` next to the installed package or the CWD."""
    candidates = [
        Path(__file__).resolve().parents[2] / "nexus" / "kb",
        Path.cwd() / "nexus" / "kb",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _parse_entry(text: str, fallback_id: str) -> dict[str, Any]:
    """Parse a KB Markdown file with a small YAML-ish frontmatter block."""
    entry: dict[str, Any] = {"id": fallback_id, "keywords": []}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            frontmatter = text[3:end].strip()
            body = text[end + 4 :].strip()
            for line in frontmatter.splitlines():
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key == "keywords":
                    entry["keywords"] = [k.strip() for k in value.split(",") if k.strip()]
                elif key:
                    entry[key] = value
            entry["body"] = body
            return entry
    entry["body"] = text.strip()
    return entry


def _load_entries() -> tuple[list[dict[str, Any]], bool]:
    """Load KB entries from disk; fall back to embedded defaults.

    Returns ``(entries, loaded_from_disk)``.
    """
    kb_dir = _find_kb_dir()
    if not kb_dir:
        return _FALLBACK_ENTRIES, False

    try:
        entries = [
            _parse_entry(path.read_text(encoding="utf-8"), path.stem)
            for path in sorted(kb_dir.glob("*.md"))
        ]
    except OSError:
        return _FALLBACK_ENTRIES, False

    return (entries, True) if entries else (_FALLBACK_ENTRIES, False)


_STOPWORDS = {
    "a", "am", "an", "and", "are", "as", "at", "be", "can", "do", "does",
    "for", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "our", "the", "to", "we", "where", "with", "you", "your",
}


def _score(entry: dict[str, Any], query_words: list[str]) -> int:
    """Weighted keyword match: title/keywords count more than body text.

    Stopwords are dropped so common words (e.g. "the", "where") in a long
    body don't outweigh a real keyword hit in a short entry.
    """
    words = [w for w in query_words if w not in _STOPWORDS] or query_words
    title = str(entry.get("title", "")).lower()
    category = str(entry.get("category", "")).lower()
    keywords = " ".join(entry.get("keywords", [])).lower()
    body = str(entry.get("body", "")).lower()
    return sum(
        title.count(w) * 3 + keywords.count(w) * 3 + category.count(w) * 2 + body.count(w)
        for w in words
    )


async def nexus_info(input_data: NexusInfoInput) -> dict:
    """Look up your org's own access-request, repo-ownership-portal, and
    documentation links from the local knowledge base (nexus/kb/*.md).

    Makes no network calls. Pass a free-text ``query`` (e.g. "raise a
    ticket for repo access", "where are the docs") to rank the most
    relevant entries first; omit it to list everything.
    """
    try:
        entries, loaded_from_disk = _load_entries()

        if input_data.query:
            query_words = re.findall(r"[a-z0-9]+", input_data.query.lower())
            scored = sorted(
                ((entry, _score(entry, query_words)) for entry in entries),
                key=lambda pair: pair[1],
                reverse=True,
            )
            matched = [entry for entry, score in scored if score > 0]
            results = matched or entries
        else:
            results = entries

        return {
            "status": "success",
            "data": {
                "query": input_data.query,
                "source": "kb" if loaded_from_disk else "embedded_fallback",
                "results": [
                    {
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "url": entry.get("url"),
                        "category": entry.get("category"),
                        "summary": entry.get("body"),
                    }
                    for entry in results
                ],
                "all_topics": [
                    {"id": entry.get("id"), "title": entry.get("title"), "url": entry.get("url")}
                    for entry in entries
                ],
            },
        }
    except OSError as e:
        return {"status": "error", "error": str(e)}
