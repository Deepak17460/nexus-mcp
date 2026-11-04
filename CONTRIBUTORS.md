# Contributors

`nexus-mcp` is a Model Context Protocol (MCP) server for Sonatype Nexus,
originally built internally and open-sourced for anyone running Sonatype
Nexus OSS/Pro who wants to use it with an MCP-capable AI client.

## Maintainer

| Name              | Role                  | Contact                                             |
| ----------------- | --------------------- | ---------------------------------------------------- |
| **Deepak Kumar**  | Maintainer            | [GitHub @Deepak17460](https://github.com/Deepak17460) |

Reach the maintainer via a GitHub issue on this repo rather than email —
it keeps the discussion visible to other contributors and searchable for
anyone hitting the same thing later.

### Areas this project covers

- MCP tool design and Nexus REST integration (`nexus_mcp/nexus_client.py`,
  `nexus_mcp/server.py`, `nexus_mcp/tools/`)
- Build, packaging, and the Docker image (`Dockerfile`,
  `docker-compose.yml`, `DOCKER_GUIDE.md`)
- Authentication, configuration, and logging
  (`nexus_mcp/config.py`, `nexus_mcp/logging_config.py`, `LOGGING_GUIDE.md`)
- Cursor & Claude client integration (`.claude/`, `.cursor/`, `.codex/`,
  README client snippets)

## Acknowledgements

Manish Raghav contributed substantially to this project's early tool
design and Nexus REST integration during its internal development.

## How to contribute

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full workflow (branching,
code style, tests, docs, and how to open a pull request), and for how to
report bugs or security issues.

## Adding yourself

If you become a regular contributor and want to be listed here, open a PR
that adds your name, role, and a link to your GitHub profile to the
section below, and get it reviewed by the maintainer.

### Additional contributors

_None yet — be the first!_
