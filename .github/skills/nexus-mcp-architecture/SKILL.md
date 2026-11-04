---
name: nexus-mcp-architecture
description: Plan or change the Nexus MCP server's Python architecture, including the server, client, Pydantic models, and tool modules.
---

# Nexus MCP Architecture

Use this skill when a request changes the server's capabilities or internal structure. Keep the responsibility boundaries used by this repository:

- `server.py` declares MCP tools, validates tool input through models, dispatches, and serializes the response.
- `tools/` owns user-oriented operation behavior and response shaping.
- `nexus_client.py` owns async Nexus REST calls and must not know about MCP protocol objects.
- `models.py` owns Pydantic input and domain models.
- `config.py` owns environment configuration and credential validation.

Before adding a tool, inspect the affected tool module, client method, input model, and tests. Make the tool name and JSON schema clear enough for an AI client to select it without reading implementation details. Preserve the existing response convention of JSON containing success data or an error.

Do not add a new Nexus endpoint merely because it seems related. Confirm the requested operation, supported Nexus edition/version, format, and required permissions first. Keep transport I/O asynchronous and avoid coupling tool code to `httpx` internals.

For a change that has side effects, also use `nexus-mcp-security`; for a behavioral change, use `nexus-mcp-testing`.
