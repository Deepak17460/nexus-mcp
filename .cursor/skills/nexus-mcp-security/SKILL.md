---
name: nexus-mcp-security
description: Harden Nexus MCP authentication, configuration, input handling, and side-effecting operations without exposing artifacts or credentials.
---

# Nexus MCP Security

Use this skill for authentication, configuration, uploads, cleanup, repository changes, or a security review. `NEXUS_URL` must use HTTPS unless the operator explicitly enables the development-only `ALLOW_INSECURE=true` override. Never weaken that default, log secrets, commit `.env` files, or bake credentials into container images.

Accept either an API token or a complete username/password pair. Error messages and logs may identify the failed configuration field or Nexus status class, but must not include tokens, passwords, authorization headers, base64 content, or full request bodies.

Treat `file_path` uploads as a local-file access boundary: constrain paths to an explicitly approved workspace or configured upload root, reject directories/symlinks escaping that root, and enforce an appropriate size limit before reading. Validate base64 strictly and impose the same size limit.

For irreversible or broad-impact Nexus actions (delete, cleanup execution, repository configuration, privilege changes), require an explicit confirmation parameter that repeats the intended target. First provide a dry-run or preview where Nexus supports it. Do not infer confirmation from a descriptive request.

Use least-privilege Nexus credentials and preserve TLS certificate validation in production.
