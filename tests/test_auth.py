import base64
import sys

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Clean environment and reload config module for each test."""
    import pathlib

    # Move .env file to prevent loading
    project_dir = pathlib.Path(__file__).parent.parent
    env_path = project_dir / ".env"
    env_backup = project_dir / ".env.backup"

    if env_path.exists():
        env_path.rename(env_backup)

    # Clear all Nexus-related env vars
    for key in [
        "NEXUS_URL",
        "NEXUS_API_TOKEN",
        "NEXUS_USERNAME",
        "NEXUS_PASSWORD",
        "ALLOW_INSECURE",
        "MCP_TRANSPORT",
        "MCP_HTTP_HOST",
        "MCP_HTTP_PORT",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Remove config module from cache to force reload
    if "nexus_mcp.config" in sys.modules:
        del sys.modules["nexus_mcp.config"]

    yield

    # Cleanup after test
    if "nexus_mcp.config" in sys.modules:
        del sys.modules["nexus_mcp.config"]

    # Restore .env file
    if env_backup.exists():
        env_backup.rename(env_path)


def test_api_token_auth(monkeypatch, clean_env):
    """Test authentication with API token."""
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("NEXUS_API_TOKEN", "test-token-123")
    monkeypatch.setenv("ALLOW_INSECURE", "true")

    from nexus_mcp.config import Config

    config = Config()
    auth_header = config.get_auth_header()

    assert "Authorization" in auth_header
    assert auth_header["Authorization"] == "Bearer test-token-123"


def test_basic_auth_username_password(monkeypatch, clean_env):
    """Test authentication with username and password."""
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("ALLOW_INSECURE", "true")
    monkeypatch.setenv("NEXUS_USERNAME", "admin")
    monkeypatch.setenv("NEXUS_PASSWORD", "password123")

    from nexus_mcp.config import Config

    config = Config()
    auth_header = config.get_auth_header()

    assert "Authorization" in auth_header
    assert auth_header["Authorization"].startswith("Basic ")

    # Verify it's proper base64 encoding
    encoded = auth_header["Authorization"].replace("Basic ", "")
    decoded = base64.b64decode(encoded).decode()
    assert decoded == "admin:password123"


def test_no_auth_raises_error(monkeypatch, clean_env):
    """Test that missing authentication raises ValueError."""
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("ALLOW_INSECURE", "true")

    from nexus_mcp.config import Config

    with pytest.raises(ValueError, match="Either NEXUS_API_TOKEN or both NEXUS_USERNAME and NEXUS_PASSWORD must be set"):
        Config()


def test_partial_credentials_raises_error(monkeypatch, clean_env):
    """Test that partial username/password raises ValueError."""
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("ALLOW_INSECURE", "true")
    monkeypatch.setenv("NEXUS_USERNAME", "admin")

    from nexus_mcp.config import Config

    with pytest.raises(ValueError, match="Either NEXUS_API_TOKEN or both NEXUS_USERNAME and NEXUS_PASSWORD must be set"):
        Config()


def test_token_takes_precedence(monkeypatch, clean_env):
    """Test that API token takes precedence over username/password."""
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("ALLOW_INSECURE", "true")
    monkeypatch.setenv("NEXUS_API_TOKEN", "token-priority")
    monkeypatch.setenv("NEXUS_USERNAME", "admin")
    monkeypatch.setenv("NEXUS_PASSWORD", "password")

    from nexus_mcp.config import Config

    config = Config()
    auth_header = config.get_auth_header()

    # Token should be used, not basic auth
    assert auth_header["Authorization"] == "Bearer token-priority"


def test_http_transport_allows_no_server_wide_auth(monkeypatch, clean_env):
    """MCP_TRANSPORT=http: no server-wide credentials required -- each
    request supplies its own (see with_basic_auth / NexusServer._resolve_client)."""
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("ALLOW_INSECURE", "true")
    monkeypatch.setenv("MCP_TRANSPORT", "http")

    from nexus_mcp.config import Config

    config = Config()  # must not raise, unlike the stdio-mode equivalent above
    assert config.mcp_transport == "http"
    assert config.nexus_username == ""
    assert config.nexus_password == ""


def test_stdio_transport_still_requires_auth(monkeypatch, clean_env):
    """Default transport (stdio) keeps requiring server-wide auth."""
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("ALLOW_INSECURE", "true")

    from nexus_mcp.config import Config

    with pytest.raises(ValueError, match="Either NEXUS_API_TOKEN or both"):
        Config()


def test_invalid_mcp_transport_raises_error(monkeypatch, clean_env):
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("ALLOW_INSECURE", "true")
    monkeypatch.setenv("NEXUS_API_TOKEN", "test-token")
    monkeypatch.setenv("MCP_TRANSPORT", "carrier-pigeon")

    from nexus_mcp.config import Config

    with pytest.raises(ValueError, match="MCP_TRANSPORT must be one of"):
        Config()


def test_invalid_mcp_http_port_raises_error(monkeypatch, clean_env):
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("ALLOW_INSECURE", "true")
    monkeypatch.setenv("NEXUS_API_TOKEN", "test-token")
    monkeypatch.setenv("MCP_HTTP_PORT", "not-a-port")

    from nexus_mcp.config import Config

    with pytest.raises(ValueError, match="MCP_HTTP_PORT must be an integer"):
        Config()


def test_with_basic_auth_overrides_only_identity(monkeypatch, clean_env):
    """with_basic_auth() swaps identity but keeps the server-wide nexus_url/
    allow_insecure/repo_info_portal_url -- used per-request in hosted mode."""
    monkeypatch.setenv("NEXUS_URL", "http://localhost:8081")
    monkeypatch.setenv("ALLOW_INSECURE", "true")
    monkeypatch.setenv("MCP_TRANSPORT", "http")

    from nexus_mcp.config import Config

    base_config = Config()
    per_request = base_config.with_basic_auth("alice", "s3cret")

    assert per_request is not base_config
    assert per_request.nexus_username == "alice"
    assert per_request.nexus_password == "s3cret"
    assert per_request.nexus_api_token == ""
    assert per_request.nexus_url == base_config.nexus_url
    assert per_request.repo_info_portal_url == base_config.repo_info_portal_url

    auth_header = per_request.get_auth_header()
    encoded = auth_header["Authorization"].removeprefix("Basic ")
    assert base64.b64decode(encoded).decode() == "alice:s3cret"

    # The original config is untouched by the override.
    assert base_config.nexus_username == ""
