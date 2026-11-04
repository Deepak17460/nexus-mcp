
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

- `nexus_mcp/server.py` — MCP server with all 11 tools registered
- `nexus_mcp/nexus_client.py` — Async HTTP client to Nexus REST API
- `nexus_mcp/config.py` — Configuration validation and auth setup
- `nexus_mcp/models.py` — Pydantic models for type-safe inputs/outputs
- `tests/` — Pytest unit tests with respx mocking

## Available MCP Tools

All tools return JSON with `status`, `data` (on success), or `error` (on failure).

### Health & Status
- **nexus_health_check** — Verify Nexus is running and credentials work

### Repository Management
- **nexus_list_repositories** — List name, format, type, online status
- **nexus_get_repository** — Get full config for one repository

### Component Operations
- **nexus_search_components** — Search with filters (repo, format, group, name, version, keyword)
- **nexus_get_component** — Get component details by ID
- **nexus_upload_component** — Upload artifacts (supports Maven, npm, Docker, raw)

### Asset Management
- **nexus_get_asset** — Retrieve asset metadata by ID

### Cleanup
- **nexus_list_cleanup_policies** — List available cleanup policies

## Code Structure

```
nexus_mcp/
├── config.py           # Config loading, validation, auth
├── models.py           # Pydantic input/output models
├── nexus_client.py     # Async httpx HTTP client
├── server.py           # MCP server + tool handlers
├── main.py             # CLI entry point
└── tools/              # Tool implementations
    ├── health.py
    ├── repositories.py
    ├── components.py
    ├── assets.py
    └── cleanup.py
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
