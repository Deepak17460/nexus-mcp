---
name: nexus-mcp-tool-design
description: Design, add, or revise MCP tools for this Nexus server, including schemas, pagination, result shape, and user-safe behavior.
---

# Nexus MCP Tool Design

Use this skill for public MCP-tool design, not for a private client-only refactor. Tool descriptions must say what the operation does, what scope it affects, and important limitations. Use JSON Schema with accurate required fields; validate structured inputs with Pydantic before making a Nexus call.

Prefer small, intention-revealing tools over one broad tool that exposes arbitrary Nexus paths or request bodies. Treat identifiers, repository names, continuation tokens, formats, and uploaded content as untrusted input. Preserve Nexus continuation tokens exactly and expose them in the result when an endpoint paginates; do not silently fetch an unbounded number of pages.

Read-only tools should be safe by default. For a mutating tool, require the minimally necessary identifying fields, surface the target repository/component in its description and result, and never make destructive actions implicit. Do not expose credentials, authorization headers, local absolute paths, or raw exception tracebacks in a tool response.

Wire a completed tool through all relevant layers: schema/model, registration and dispatch in `server.py`, tool implementation, Nexus client operation, and mocked tests.
