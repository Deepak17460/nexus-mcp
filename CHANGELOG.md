# Changelog

All notable changes to `nexus-mcp` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project does not yet follow strict semantic-version tagging in git —
entries below are grouped by theme rather than by release tag.

## [Unreleased]

- Added architecture and request-flow diagrams to `README.md`
  (`docs/architecture.mmd`, `docs/request-flow.mmd`, rendered to PNG via
  `mermaid-cli`).
- Documented multiple ways to generate the hosted-mode Basic auth header
  (Python one-liner, `base64`, PowerShell), alongside the recommended
  `nexus_mcp.make_basic_auth_header` CLI helper.
- Fixed `/mcp` issuing a `307` redirect that downgraded `https://` to
  `http://` behind a TLS-terminating proxy/ALB, breaking MCP client
  connections (`Route` + raw ASGI app instead of `Mount`).
- Added a CI/CD stage (`deploy-http-container`) that keeps a hosted
  Streamable HTTP container up to date after every pipeline run.

## [0.1.0] — Hosted multi-user deployment, richer tool set

### Added
- **Hosted Streamable HTTP transport** (`MCP_TRANSPORT=http`): a single
  shared server process where each request carries its own Nexus identity
  via an `Authorization: Basic` header, resolved into a fresh,
  request-scoped `NexusClient` — never cached or shared across callers.
- `nexus_mcp.make_basic_auth_header` CLI helper to generate that header.
- `nexus_get_repository_owner` — looks up repository ownership via the
  Repo Info portal's `repositories.json` feed.
- `nexus_get_dependency_snippet` — build-tool dependency snippets, with
  correct Docker pull-address resolution for nginx-fronted deployments.
- `nexus_get_latest_release`, `nexus_check_artifact_exists`,
  `nexus_get_download_url`, `nexus_download_asset`,
  `nexus_get_component_versions`, `nexus_check_writable`,
  `nexus_get_artifact_age_report`, `nexus_info` (knowledge-base lookup).
- GitLab CI pipeline: build/publish the Docker image, then keep a hosted
  HTTP container continuously up to date on each successful pipeline run.

### Changed
- `nexus_health_check` no longer parses `GET /v1/status` as JSON (it has
  no response body) and no longer reports edition/version.

### Removed
- Repository- and cleanup-policy-mutating tools (kept the surface
  read-oriented and safe by default); `nexus_list_cleanup_policies` was
  also dropped as unnecessary.

### Fixed
- `nexus_get_repository_owner` portal parsing, rewritten to match the
  real page structure and to fetch `repositories.json` directly instead
  of scraping HTML.

## Initial commit

- Initial Nexus MCP server: health check, repository listing/inspection,
  component search/upload, asset retrieval, cleanup-policy listing.
