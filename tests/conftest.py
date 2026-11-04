import os

import pytest


@pytest.fixture
def mock_config():
    """Setup mock environment variables."""
    os.environ["NEXUS_URL"] = "http://localhost:8081"
    os.environ["NEXUS_API_TOKEN"] = "test-token"
    os.environ["ALLOW_INSECURE"] = "true"
    # No default in Config -- set explicitly so tests exercising
    # nexus_get_repository_owner have a portal URL configured.
    os.environ["NEXUS_REPO_INFO_URL"] = "https://portal.example/nexus-repo-info/"
    yield
    # Cleanup
    for key in ["NEXUS_URL", "NEXUS_API_TOKEN", "ALLOW_INSECURE", "NEXUS_REPO_INFO_URL"]:
        os.environ.pop(key, None)


@pytest.fixture
def config(mock_config):
    """Return a Config instance."""
    from nexus_mcp.config import Config

    return Config()


@pytest.fixture
def nexus_client(config):
    """Return a NexusClient instance."""
    from nexus_mcp.nexus_client import NexusClient

    return NexusClient(config)
