# Nexus MCP Claude Resources

This directory contains project-local guidance for safely building and operating this Sonatype Nexus MCP server. `CLAUDE.md` is the concise project guide; use the skills below for task-specific instructions. These mirror the skills in `.codex/skills/` and `.cursor/skills/` so guidance stays consistent across assistants.

| Skill | Use when |
| --- | --- |
| [nexus-mcp-architecture](skills/nexus-mcp-architecture/SKILL.md) | Changing server structure, tool modules, models, or client boundaries. |
| [nexus-mcp-tool-design](skills/nexus-mcp-tool-design/SKILL.md) | Adding or revising MCP schemas, pagination, result shapes, or tool behavior. |
| [nexus-mcp-nexus-api](skills/nexus-mcp-nexus-api/SKILL.md) | Calling or reviewing Sonatype Nexus REST endpoints and repository-format behavior. |
| [nexus-mcp-security](skills/nexus-mcp-security/SKILL.md) | Handling credentials, configuration, uploads, cleanup, or other side-effecting operations. |
| [nexus-mcp-testing](skills/nexus-mcp-testing/SKILL.md) | Writing tests, diagnosing defects, or verifying behavior with pytest and respx. |
| [nexus-mcp-operations](skills/nexus-mcp-operations/SKILL.md) | Configuring stdio clients, Docker, CI, logging, deployment, or runtime troubleshooting. |

## Local Development

```powershell
pip install -e ".[dev]"
pytest
ruff check .
mypy nexus_mcp
```

Set `NEXUS_URL` and either `NEXUS_API_TOKEN` or `NEXUS_USERNAME` plus `NEXUS_PASSWORD` only in your local environment or approved secret store. See the repository root [README.md](../README.md) for installation, client integration, and Docker usage.
