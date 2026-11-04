import base64

import pytest

from nexus_mcp.http_auth import AuthenticationRequiredError, parse_basic_auth_header


def _basic_header(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


def test_parse_basic_auth_header_valid():
    username, password = parse_basic_auth_header(_basic_header("alice", "s3cret"))
    assert username == "alice"
    assert password == "s3cret"


def test_parse_basic_auth_header_password_may_contain_colons():
    username, password = parse_basic_auth_header(_basic_header("alice", "pa:ss:w0rd"))
    assert username == "alice"
    assert password == "pa:ss:w0rd"


def test_parse_basic_auth_header_case_insensitive_scheme():
    username, password = parse_basic_auth_header(
        "bAsIc " + base64.b64encode(b"alice:s3cret").decode()
    )
    assert username == "alice"
    assert password == "s3cret"


@pytest.mark.parametrize(
    "header_value",
    [
        "",
        "Basic",
        "Bearer sometoken",
        "Basic ",
    ],
)
def test_parse_basic_auth_header_missing_or_wrong_scheme(header_value):
    with pytest.raises(AuthenticationRequiredError):
        parse_basic_auth_header(header_value)


def test_parse_basic_auth_header_malformed_base64():
    with pytest.raises(AuthenticationRequiredError):
        parse_basic_auth_header("Basic not-valid-base64!!")


def test_parse_basic_auth_header_no_colon_separator():
    encoded = base64.b64encode(b"just-a-username-no-password").decode()
    with pytest.raises(AuthenticationRequiredError):
        parse_basic_auth_header(f"Basic {encoded}")


def test_parse_basic_auth_header_empty_username():
    encoded = base64.b64encode(b":password-only").decode()
    with pytest.raises(AuthenticationRequiredError):
        parse_basic_auth_header(f"Basic {encoded}")


def test_parse_basic_auth_header_error_never_echoes_credentials():
    """The error message must not leak the raw header value or decoded
    credentials -- it should only describe the expected format."""
    header = _basic_header("super-secret-user", "super-secret-pass")
    try:
        parse_basic_auth_header("Bearer " + header)
    except AuthenticationRequiredError as e:
        assert "super-secret-user" not in str(e)
        assert "super-secret-pass" not in str(e)
    else:
        pytest.fail("Expected AuthenticationRequiredError")
