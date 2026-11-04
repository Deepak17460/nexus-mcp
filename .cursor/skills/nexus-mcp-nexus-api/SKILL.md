---
name: nexus-mcp-nexus-api
description: Implement or review Sonatype Nexus Repository REST API integration in the Nexus MCP server.
---

# Nexus REST API Integration

Use this skill when changing code that calls Nexus. Keep all HTTP calls in `NexusClient`, using the configured base URL of `<NEXUS_URL>/service/rest/v1` and `httpx.AsyncClient`. URL-encode path parameters when they are used as a path segment; use `params` for query values.

Check the Nexus REST API documentation for the target Nexus edition and version before implementing an endpoint whose availability, request shape, or format support is uncertain. Do not assume upload conventions are shared across raw, Maven, npm, Docker, and other repository formats. Model each supported format explicitly or reject unsupported formats with an actionable error.

Set practical timeouts and retain enough HTTP status/context for callers to distinguish bad input, authentication/authorization failures, missing resources, and server failures. Never return Nexus response bodies verbatim when they may contain sensitive details. Reuse the configured authorization header and do not construct credentials in individual methods.

For uploads, validate exactly one content source, bound any decoded payload before holding it in memory, and close file handles deterministically. Add `respx` tests that assert method, URL, query parameters, request body shape where relevant, and error mapping.
