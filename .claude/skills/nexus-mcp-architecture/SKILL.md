---
name: nexus-mcp-architecture
description: Plan or change the Nexus MCP server's Python architecture, including the server, client, Pydantic models, and tool modules.
---

# Nexus MCP Architecture

Use this skill when a request changes the server's capabilities or internal structure. Keep the responsibility boundaries used by this repository:

- `server.py` declares MCP tools, validates tool input through models, dispatches, and serializes the response. `NexusServer._resolve_client()` also picks which `NexusClient` a given call uses (server-configured for stdio; a fresh, request-scoped one built from a per-request header for hosted HTTP) — dispatch branches must call this rather than reaching for `self.client` directly.
- `tools/` owns user-oriented operation behavior and response shaping.
- `nexus_client.py` owns async Nexus REST calls and must not know about MCP protocol objects.
- `models.py` owns Pydantic input and domain models.
- `config.py` owns environment configuration and credential validation, including transport selection (`mcp_transport`/`mcp_http_host`/`mcp_http_port`) and `with_basic_auth()`, which produces the per-request config override used in hosted mode.
- `http_app.py`/`http_auth.py` own the hosted Streamable HTTP transport and its per-request Basic-auth header parsing respectively — kept separate from `server.py`/`nexus_client.py` since neither is Nexus-specific or stdio-specific.

Before adding a tool, inspect the affected tool module, client method, input model, and tests. Make the tool name and JSON schema clear enough for an AI client to select it without reading implementation details. Preserve the existing response convention of JSON containing success data or an error.

Do not add a new Nexus endpoint merely because it seems related. Confirm the requested operation, supported Nexus edition/version, format, and required permissions first. Keep transport I/O asynchronous and avoid coupling tool code to `httpx` internals.

For a change that has side effects, also use `nexus-mcp-security`; for a behavioral change, use `nexus-mcp-testing`.
