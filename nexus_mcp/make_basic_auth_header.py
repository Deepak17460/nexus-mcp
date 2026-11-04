"""One-time helper: generate the 'Authorization: Basic <...>' header value a
user pastes into their own MCP client config to authenticate to a hosted
Nexus MCP server (``MCP_TRANSPORT=http``). Never sends the result anywhere
and never stores it — it's printed once so it can be copied into a client
config or a local environment variable.

Usage::

    python -m nexus_mcp.make_basic_auth_header
"""

from __future__ import annotations

import base64
import getpass


def main() -> None:
    username = input("Nexus username: ").strip()
    if not username:
        print("Username is required.")
        raise SystemExit(1)

    password = getpass.getpass("Nexus password: ")
    if not password:
        print("Password is required.")
        raise SystemExit(1)

    header_value = f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}"

    print(
        "\nUse this as the Authorization header value in your MCP client "
        "config (e.g. store it as NEXUS_MCP_AUTH in your own environment "
        "and reference it as ${env:NEXUS_MCP_AUTH} in mcp.json — see the "
        "README's 'Hosted / Multi-user Deployment' section):\n"
    )
    print(header_value)
    print(
        "\nThis value is equivalent to your password — store it the same "
        "way you would a password (a local env var, a secrets manager, "
        "etc.), never in a file committed to source control."
    )


if __name__ == "__main__":
    main()
