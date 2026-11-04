"""Per-request Basic-auth extraction for the hosted Streamable HTTP transport
(``MCP_TRANSPORT=http``). Stdio deployments never import or exercise this
module — see ``NexusServer._resolve_client()`` in ``server.py``.
"""

from __future__ import annotations

import base64
import binascii


class AuthenticationRequiredError(Exception):
    """Raised when a hosted-mode HTTP request has no usable Authorization
    header. Its message is safe to return to the caller as-is: it explains
    what's expected but never echoes back any credential material."""


def parse_basic_auth_header(header_value: str) -> tuple[str, str]:
    """Parse an ``Authorization: Basic <base64(username:password)>`` header
    into ``(username, password)``.

    Raises ``AuthenticationRequiredError`` for anything else — a missing or
    non-Basic scheme, malformed base64/UTF-8, or a decoded value with no
    ``:`` separator or empty username — rather than guessing at partial or
    malformed credentials.
    """
    scheme, _, encoded = header_value.strip().partition(" ")
    if scheme.lower() != "basic" or not encoded:
        raise AuthenticationRequiredError(
            "Expected an 'Authorization: Basic <base64(username:password)>' header."
        )

    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as e:
        raise AuthenticationRequiredError(
            "Authorization header's Basic credentials could not be decoded."
        ) from e

    username, sep, password = decoded.partition(":")
    if not sep or not username:
        raise AuthenticationRequiredError(
            "Authorization header's Basic credentials must be in 'username:password' form."
        )
    return username, password
