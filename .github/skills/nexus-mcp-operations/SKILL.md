---
name: nexus-mcp-operations
description: Package, configure, deploy, or troubleshoot this stdio-based Nexus MCP server in Python or Docker.
---

# Nexus MCP Operations

Use this skill for runtime configuration, containerization, deployment, observability, or MCP-client setup. This server uses MCP stdio: its container must run with standard input open (`-i`), must not allocate a TTY (`-t`), and is started by the MCP client rather than run as a detached HTTP service.

Keep configuration runtime-provided through `NEXUS_URL` plus either `NEXUS_API_TOKEN` or `NEXUS_USERNAME`/`NEXUS_PASSWORD`. Do not add secrets to Dockerfiles, compose files, image layers, source control, or process logs. Production configurations use HTTPS; `ALLOW_INSECURE=true` is only appropriate for an explicitly chosen development environment.

When changing Docker or CI, preserve reproducible builds and validate the installed `nexus-mcp` entry point in a short-lived container. Ensure logs go to stderr or configured files so stdout remains clean for MCP protocol messages. Make operational errors actionable without echoing credential material.

Diagnose connection failures in this order: configuration validity, DNS/network reachability, TLS/CA trust, Nexus status endpoint, then authorization and repository permissions. Consult `DOCKER_GUIDE.md` and `LOGGING_GUIDE.md` only for Docker or logging-specific work.
