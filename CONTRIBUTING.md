# Contributing to nexus-mcp

`nexus-mcp` is open source and welcomes contributions from anyone. See
[`CONTRIBUTORS.md`](CONTRIBUTORS.md) for the current maintainer and how to
get in touch.

To keep the tool stable for everyone depending on it, please follow this
workflow:

1. **Open an issue first** on this GitHub repo describing the bug or
   feature, so we can discuss the approach before you invest time in a PR.
2. **Fork the repo and create a feature branch** off `main` — use a short,
   descriptive name like `feat/download-component` or
   `fix/repository-size-pagination`.
3. **Follow the existing code style.** Before pushing, run:
   ```bash
   ruff check .
   mypy nexus_mcp
   pytest
   ```
4. **Add or update tests** under `tests/` for any behavior change. Tools
   that hit the Nexus REST API should be covered with mocked `httpx`
   responses in the same style as `tests/test_repositories.py`.
5. **Update the docs.** If you add or rename a tool, update:
   - The tool schema list in `nexus_mcp/server.py`
   - The "Available Tools" section of `README.md`
   - The relevant skill file under `.claude/skills/` (and its mirrors under
     `.codex/skills/` and `.cursor/skills/`)
   - `CHANGELOG.md`, under an `[Unreleased]` entry
6. **Open a pull request** targeting `main` and request review from the
   maintainer. We aim to review within a few days.

## Reporting issues

- **Bugs / regressions:** open a GitHub issue with the Nexus edition
  (OSS/Pro), Nexus version, MCP client (Cursor / Claude / other), the
  failing tool name, and the sanitized error output. Never paste raw
  credentials.
- **Security issues:** please use GitHub's private
  ["Report a vulnerability"](https://github.com/Deepak17460/nexus-mcp/security/advisories/new)
  flow instead of a public issue.

## Becoming a listed contributor

If you become a regular contributor and want to be listed in
`CONTRIBUTORS.md`, open a PR that adds your name, role, and a link to your
GitHub profile under its "Additional contributors" section, and get it
reviewed by the maintainer.
