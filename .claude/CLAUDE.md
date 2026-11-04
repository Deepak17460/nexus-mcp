
# Nexus MCP Project Configuration

This is a Sonatype Nexus OSS MCP (Model Context Protocol) server for Python. Use this guide to understand the project structure and available operations.

## Project Overview

A complete async Python MCP server that connects Claude to Sonatype Nexus OSS, enabling repository management, component search, asset inspection, and cleanup operations through the Nexus REST API.

## Quick Start

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run the server
nexus-mcp

# Or run tests
pytest
```

## Environment Setup

Copy `.env.example` to `.env` and configure:

```env
NEXUS_URL=http://localhost:8081
NEXUS_API_TOKEN=your-token
# Or: NEXUS_USERNAME=admin, NEXUS_PASSWORD=password
ALLOW_INSECURE=true  # Dev only, not for production
```

## Key Files

- `nexus_mcp/server.py` — MCP server with all 21 tools registered
- `nexus_mcp/nexus_client.py` — Async HTTP client to Nexus REST API
- `nexus_mcp/config.py` — Configuration validation and auth setup
- `nexus_mcp/models.py` — Pydantic models for type-safe inputs/outputs
- `nexus_mcp/http_app.py` / `http_auth.py` — Optional hosted Streamable HTTP
  transport and its per-request Basic-auth parsing (see README's "Hosted /
  Multi-user Deployment" section) — not used in the default stdio setup
- `tests/` — Pytest unit tests with respx mocking

## Available MCP Tools

All tools return JSON with `status`, `data` (on success), or `error` (on failure).
See the root [README.md](../README.md#available-tools) for the full,
up-to-date list and description of all 21 tools — summarized by category
below so this stays a quick reference, not a second source of truth:

- **Health & Status** — `nexus_health_check`, `nexus_check_writable`
- **Repository Management** — `nexus_list_repositories`, `nexus_get_repository`,
  `nexus_get_repository_size`
- **Component Operations** — `nexus_search_components`, `nexus_get_component`,
  `nexus_get_component_versions`, `nexus_get_latest_release`,
  `nexus_check_artifact_exists`, `nexus_get_dependency_snippet`,
  `nexus_upload_component`, `nexus_download_component`
- **Asset Management** — `nexus_get_asset`, `nexus_get_download_url`,
  `nexus_download_asset`
- **Activity** — `nexus_latest_uploaded_artifacts`,
  `nexus_latest_downloaded_artifacts`, `nexus_get_artifact_age_report`
- **Help & Links** — `nexus_info`, `nexus_get_repository_owner`

## Code Structure

```
nexus_mcp/
├── config.py           # Config loading, validation, auth, with_basic_auth()
├── models.py            # Pydantic input/output models
├── nexus_client.py      # Async httpx HTTP client
├── repo_info_portal.py  # Optional repo-ownership-portal client
├── server.py             # MCP server + tool handlers
├── http_app.py           # Hosted Streamable HTTP ASGI app (optional)
├── http_auth.py          # Per-request Basic-auth header parsing (optional)
├── make_basic_auth_header.py  # CLI helper for the hosted header value
├── main.py                # CLI entry point
└── tools/                 # Tool implementations
    ├── health.py
    ├── repositories.py   # incl. nexus_get_repository_owner
    ├── components.py
    ├── assets.py
    ├── activity.py
    └── info.py            # Local KB lookup (nexus_info)
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=nexus_mcp

# Run specific test
pytest tests/test_health.py
```

Tests use `respx` to mock Nexus HTTP endpoints. No real Nexus required.

## Code Quality

```bash
# Lint with ruff
ruff check .

# Type check with mypy
mypy nexus_mcp

# Auto-fix linting issues
ruff check . --fix
```

## Development Notes

- All HTTP calls are async (httpx.AsyncClient)
- Tool handlers catch specific exceptions (httpx.HTTPError, OSError, ValueError) — never bare `Exception`
- Pydantic models enforce type safety for all inputs
- Security: HTTPS required by default; tokens never logged
- For destructive operations (delete), require explicit confirmation

## MCP Integration

### Claude CLI
Add to `~/.claude/profiles.json` or `claude.json`:

```json
{
  "mcpServers": {
    "nexus": {
      "command": "nexus-mcp",
      "env": {
        "NEXUS_URL": "http://localhost:8081",
        "NEXUS_API_TOKEN": "your-token",
        "ALLOW_INSECURE": "true"
      }
    }
  }
}
```

### Claude Desktop
Add to `~/.claude/claude.json`:

```json
{
  "mcpServers": {
    "nexus": {
      "command": "python",
      "args": ["-m", "nexus_mcp.main"],
      "env": {
        "NEXUS_URL": "http://localhost:8081",
        "NEXUS_API_TOKEN": "your-token"
      }
    }
  }
}
```

## Testing with Docker

Run a local Nexus instance for development/testing:

```bash
docker run -d -p 8081:8081 --name nexus sonatype/nexus3:latest
```

Then set:
```env
NEXUS_URL=http://localhost:8081
NEXUS_API_TOKEN=your-token
ALLOW_INSECURE=true
```

Default credentials after startup: `admin` / `admin123`

## Common Workflows

### List all repositories
Use `nexus_list_repositories` tool with no parameters to get all repos with their format, type, and online status.

### Search for a component
Use `nexus_search_components` with optional filters:
- `name`: component name
- `version`: specific version
- `format`: maven2, npm, docker, etc.
- `repository`: limit to one repo

### Upload an artifact
Use `nexus_upload_component` with:
- `repository`: target repo name
- `format`: component format
- `file_path` or `file_base64`: the file to upload
- For Maven: add `group_id`, `artifact_id`, `version`, `packaging`

## Troubleshooting

**Connection refused:** Verify NEXUS_URL and that Nexus is running.

**Auth failed:** Check NEXUS_API_TOKEN or username/password in .env.

**HTTPS error:** Use `ALLOW_INSECURE=true` for self-signed certs in dev only.

**Import errors:** Run `pip install -e ".[dev]"` in the project directory.

## Skills

The focused instructions for architecture, MCP tool design, Nexus REST integration, security, testing, and operations are in [README.md](README.md). Use the skill whose scope matches the task; combine security and testing with any side-effecting capability change. These mirror the skills in `.codex/skills/` and `.cursor/skills/`.

## References

- [Nexus REST API Docs](https://help.sonatype.com/repomanager3/rest-and-integration-api)
- [MCP Specification](https://modelcontextprotocol.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
