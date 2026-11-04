import pytest

from nexus_mcp.models import NexusInfoInput
from nexus_mcp.tools.info import nexus_info


@pytest.mark.asyncio
async def test_nexus_info_no_query_lists_all_topics():
    """Omitting query returns every known KB entry."""
    result = await nexus_info(NexusInfoInput())

    assert result["status"] == "success"
    ids = {item["id"] for item in result["data"]["all_topics"]}
    assert {
        "access-request-example",
        "repo-info-portal-example",
        "documentation-example",
    } <= ids
    # With no query, results == all entries.
    assert len(result["data"]["results"]) == len(result["data"]["all_topics"])


@pytest.mark.asyncio
async def test_nexus_info_query_ranks_access_request_first():
    """A ticket/access-related query should surface the access-request entry first."""
    result = await nexus_info(NexusInfoInput(query="how do I raise a ticket for access"))

    assert result["status"] == "success"
    assert result["data"]["results"][0]["id"] == "access-request-example"
    assert "example.com" in result["data"]["results"][0]["url"]


@pytest.mark.asyncio
async def test_nexus_info_query_ranks_documentation_first():
    """A documentation-related query should surface the documentation entry first."""
    result = await nexus_info(NexusInfoInput(query="where is the documentation guide wiki"))

    assert result["status"] == "success"
    assert result["data"]["results"][0]["id"] == "documentation-example"


@pytest.mark.asyncio
async def test_nexus_info_unmatched_query_falls_back_to_all_entries():
    """A query matching nothing still returns something useful, not an empty list."""
    result = await nexus_info(NexusInfoInput(query="xyzzy quux unrelated gibberish"))

    assert result["status"] == "success"
    assert len(result["data"]["results"]) >= 1


@pytest.mark.asyncio
async def test_nexus_info_reads_from_real_kb_directory():
    """The on-disk nexus/kb directory should be found and used (not the fallback)."""
    result = await nexus_info(NexusInfoInput())

    assert result["data"]["source"] == "kb"
