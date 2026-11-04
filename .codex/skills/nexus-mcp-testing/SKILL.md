---
name: nexus-mcp-testing
description: Test or verify Nexus MCP server behavior with pytest, respx, contract-focused assertions, and quality checks.
---

# Nexus MCP Testing

Use this skill when changing behavior or investigating a defect. Tests in this repository must not need a live Nexus instance: use `pytest`, `pytest-asyncio`, and `respx` to mock Nexus REST traffic.

Cover the observable contract, not only implementation branches. For a client change, assert the HTTP method, final URL, parameters, headers when useful, request body shape, successful response parsing, and representative 4xx/5xx behavior. For an MCP tool change, test input validation, dispatch, and JSON response shape, including missing required input and unknown tools where applicable.

Keep secrets out of fixtures, snapshots, exception assertions, and test output. Add regression coverage for each fixed bug. Avoid testing against externally hosted Nexus URLs unless the user explicitly asks for an integration test and supplies a safe environment.

Run the narrow test file while iterating, then run `pytest`, `ruff check .`, and `mypy nexus_mcp` before handoff when the changed code and environment permit. Report any command that could not run and why.
