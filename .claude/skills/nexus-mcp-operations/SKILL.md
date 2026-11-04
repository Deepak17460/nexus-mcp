---
name: nexus-mcp-operations
description: Package, configure, deploy, or troubleshoot this Nexus MCP server (stdio or hosted Streamable HTTP) in Python or Docker.
---

# Nexus MCP Operations

Use this skill for runtime configuration, containerization, deployment, observability, or MCP-client setup. This server supports two transports, chosen via `MCP_TRANSPORT` (default `stdio`):

- **stdio** (default, unchanged): one process per user, started by the MCP client itself. Its container must run with standard input open (`-i`), must not allocate a TTY (`-t`), and is not a detached HTTP service. Credentials (`NEXUS_URL` plus either `NEXUS_API_TOKEN` or `NEXUS_USERNAME`/`NEXUS_PASSWORD`) are required and loaded once at startup from the environment.
- **http** (`MCP_TRANSPORT=http`, see `http_app.py`/`http_auth.py`): a single, network-reachable process shared by many users, run as a normal long-lived service (e.g. `docker run -p ...`, no `-i`/`-t`). There is no single server-wide identity — leave `NEXUS_USERNAME`/`NEXUS_PASSWORD`/`NEXUS_API_TOKEN` unset; each request instead carries its own `Authorization: Basic <base64(username:password)>` header, and `NexusServer._resolve_client()` builds a fresh, request-scoped client from it (never cached, never falls back to a shared identity). This process must sit behind a TLS-terminating reverse proxy (it only listens on plain HTTP internally) since Basic auth sends real credentials on every request. `GET /healthz` is a credential-free liveness probe; the MCP endpoint is `/mcp`. See the README's "Hosted / Multi-user Deployment" section for the full client-config pattern.

Keep configuration runtime-provided. Do not add secrets to Dockerfiles, compose files, image layers, source control, or process logs. Production configurations use HTTPS; `ALLOW_INSECURE=true` is only appropriate for an explicitly chosen development environment.

When changing Docker or CI, preserve reproducible builds and validate the installed `nexus-mcp` entry point in a short-lived container. Ensure logs go to stderr or configured files so stdout remains clean for MCP protocol messages (stdio mode) or application logs (http mode). Make operational errors actionable without echoing credential material.

Diagnose connection failures in this order: configuration validity (including `MCP_TRANSPORT`/`MCP_HTTP_HOST`/`MCP_HTTP_PORT` for hosted mode), DNS/network reachability, TLS/CA trust, Nexus status endpoint, then authorization and repository permissions. For hosted mode specifically, first confirm the caller's `Authorization` header actually reached the process (reverse proxies sometimes strip or rewrite it) before assuming a Nexus-side auth problem. Consult `DOCKER_GUIDE.md` and `LOGGING_GUIDE.md` only for Docker or logging-specific work.
