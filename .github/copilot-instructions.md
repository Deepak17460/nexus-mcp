# Nexus MCP Project Guide for GitHub Copilot

This repository is a Python 3.11+ MCP server that exposes a safe, focused
interface to Sonatype Nexus Repository OSS. It uses the MCP stdio transport
(or an optional hosted Streamable HTTP transport) and asynchronous `httpx`
calls.

## Start Here

Read the relevant source before changing a capability:

- `nexus_mcp/server.py` registers tools and dispatches MCP calls.
- `nexus_mcp/tools/` implements user-facing operations and response shaping.
- `nexus_mcp/nexus_client.py` contains Nexus REST API calls.
- `nexus_mcp/models.py` defines Pydantic input and domain models.
- `nexus_mcp/config.py` validates configuration and authentication.
- `tests/` uses pytest and respx; tests must not need a live Nexus server.

## Project Rules

- Keep HTTP I/O asynchronous and inside `NexusClient`.
- Add a tool across every necessary layer: model/schema, server
  registration and dispatch, tool implementation, client method, and tests.
- Treat Nexus endpoint availability and upload behavior as format- and
  version-specific; verify uncertain REST API details before implementation.
- Do not log or commit credentials, authorization headers, uploaded
  contents, or `.env` files.
- Preserve HTTPS by default. `ALLOW_INSECURE=true` is a development-only
  explicit override.
- Treat uploads and any future delete, cleanup-execution, or
  repository-changing operation as security-sensitive. Require clear target
  information and explicit confirmation for irreversible effects.
- Keep stdout reserved for the MCP stdio protocol. Operational logging
  belongs on stderr or configured log files.

## Verification

Use the narrowest relevant test while iterating. Before handoff, run what
applies:

```bash
pytest
ruff check .
mypy nexus_mcp
```

For container changes, also build the image and verify that `nexus-mcp` can
start in a short-lived stdio container. Do not use a real production Nexus
instance unless the user explicitly authorizes it.

## Skills

The focused instructions for architecture, MCP tool design, Nexus REST
integration, security, testing, and operations are in
[`.github/skills/`](skills/) (mirrored in `.codex/skills/` and
`.cursor/skills/` so guidance stays consistent across assistants). Use the
skill whose scope matches the task; combine security and testing with any
side-effecting capability change.
