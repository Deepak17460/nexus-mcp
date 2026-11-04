import copy
import os
from urllib.parse import urlparse

from dotenv import load_dotenv

from nexus_mcp.logging_config import get_logger

logger = get_logger(__name__)

_VALID_TRANSPORTS = ("stdio", "http")


class Config:
    """Configuration loader for Nexus MCP server."""

    def __init__(self):
        load_dotenv()
        self.nexus_url = os.getenv("NEXUS_URL", "").strip()
        self.nexus_api_token = os.getenv("NEXUS_API_TOKEN", "").strip()
        self.nexus_username = os.getenv("NEXUS_USERNAME", "").strip()
        self.nexus_password = os.getenv("NEXUS_PASSWORD", "").strip()
        self.allow_insecure = os.getenv("ALLOW_INSECURE", "").lower() == "true"
        # Optional: a separate internal portal (not Nexus's REST API, and
        # not something every Nexus deployment has) that lists each
        # repository's owner. Its own data comes from a relative
        # repositories.json fetched by the page's JS (see
        # repo_info_portal.py) -- this is the portal page URL that file is
        # resolved against. No default on purpose -- this is specific to
        # orgs that run such a portal; nexus_get_repository_owner returns a
        # clear "not configured" error when this is unset.
        self.repo_info_portal_url = os.getenv("NEXUS_REPO_INFO_URL", "").strip()

        # Transport for this server process.
        #
        # "stdio" (default): one process per user, spawned by the MCP
        # client itself. Credentials come from NEXUS_USERNAME/PASSWORD or
        # NEXUS_API_TOKEN above and are required -- unchanged from every
        # version of this server before hosted mode existed.
        #
        # "http": a single, network-reachable process shared by many users
        # (see http_app.py). There is no single "the" identity for a shared
        # process, so server-wide Nexus credentials become optional here --
        # each request instead carries its own
        # 'Authorization: Basic <base64(username:password)>' header (see
        # http_auth.py / NexusServer._resolve_client()), and this server
        # never falls back to any server-wide credentials for an HTTP
        # request even if they happen to be set.
        self.mcp_transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
        self.mcp_http_host = os.getenv("MCP_HTTP_HOST", "0.0.0.0").strip()
        self.mcp_http_port = os.getenv("MCP_HTTP_PORT", "8000").strip()

        self._validate()

    def _validate(self):
        """Validate configuration."""
        logger.debug("Validating configuration")

        if self.mcp_transport not in _VALID_TRANSPORTS:
            logger.error(f"Invalid MCP_TRANSPORT: {self.mcp_transport}")
            raise ValueError(f"MCP_TRANSPORT must be one of {_VALID_TRANSPORTS}, got '{self.mcp_transport}'")

        try:
            self.mcp_http_port = int(self.mcp_http_port)
        except ValueError:
            logger.error(f"Invalid MCP_HTTP_PORT: {self.mcp_http_port}")
            raise ValueError(f"MCP_HTTP_PORT must be an integer, got '{self.mcp_http_port}'") from None

        if not self.nexus_url:
            logger.error("NEXUS_URL environment variable is missing")
            raise ValueError("NEXUS_URL environment variable is required")

        logger.debug(f"NEXUS_URL set to: {self.nexus_url}")

        # Validate URL format
        parsed = urlparse(self.nexus_url)
        if not parsed.scheme:
            logger.error("NEXUS_URL missing scheme")
            raise ValueError("NEXUS_URL must include scheme (http:// or https://)")

        # Check HTTPS requirement
        if parsed.scheme == "http" and not self.allow_insecure:
            logger.error("NEXUS_URL uses insecure http:// without ALLOW_INSECURE=true")
            raise ValueError(
                "NEXUS_URL uses http:// which is insecure. "
                "Use https:// or set ALLOW_INSECURE=true to override."
            )

        if parsed.scheme == "http":
            logger.warning("Using insecure HTTP connection (ALLOW_INSECURE=true)")

        # Ensure URL doesn't have trailing slash
        self.nexus_url = self.nexus_url.rstrip("/")

        # Validate auth. Required for "stdio" (one process = one identity).
        # Optional for "http": each request supplies its own Basic-auth
        # credentials, and NexusServer never falls back to server-wide
        # credentials for an HTTP request -- so leaving these unset is the
        # normal, expected hosted-mode configuration, not an error.
        has_auth = bool(self.nexus_api_token) or bool(self.nexus_username and self.nexus_password)
        if self.mcp_transport == "stdio" and not has_auth:
            logger.error("No valid authentication method configured")
            raise ValueError(
                "Either NEXUS_API_TOKEN or both NEXUS_USERNAME and NEXUS_PASSWORD must be set"
            )

        if self.nexus_api_token:
            logger.info("Using API Token authentication")
        elif has_auth:
            logger.info(f"Using Username/Password authentication (user: {self.nexus_username})")
        else:
            logger.info(
                "No server-wide Nexus credentials configured -- expecting a "
                "per-request Authorization header on every call (hosted mode)"
            )

    def get_auth_header(self) -> dict[str, str]:
        """Get Authorization header for requests."""
        if self.nexus_api_token:
            return {"Authorization": f"Bearer {self.nexus_api_token}"}

        import base64

        credentials = base64.b64encode(
            f"{self.nexus_username}:{self.nexus_password}".encode()
        ).decode()
        return {"Authorization": f"Basic {credentials}"}

    def with_basic_auth(self, username: str, password: str) -> "Config":
        """Return a shallow copy of this config carrying different Basic-auth
        credentials, for a single hosted-mode (MCP_TRANSPORT=http) request.

        Keeps nexus_url/allow_insecure/repo_info_portal_url from this
        (server-wide) config — only the caller's identity changes. The
        returned Config is not re-validated (validation already ran for
        the base config), so an unrelated request's malformed value here
        can't crash the server.
        """
        override = copy.copy(self)
        override.nexus_username = username
        override.nexus_password = password
        override.nexus_api_token = ""
        return override
