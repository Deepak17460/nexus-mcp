import asyncio
import os
import sys
from argparse import ArgumentParser
from getpass import getpass

from nexus_mcp.logging_config import setup_logging
from nexus_mcp.server import NexusServer

logger = setup_logging()


def prompt_for_credentials() -> None:
    """Prompt user for Nexus credentials if not in environment."""
    logger.debug("Checking for existing credentials in environment")
    nexus_url = os.getenv("NEXUS_URL", "").strip()
    nexus_token = os.getenv("NEXUS_API_TOKEN", "").strip()
    nexus_username = os.getenv("NEXUS_USERNAME", "").strip()
    nexus_password = os.getenv("NEXUS_PASSWORD", "").strip()

    # If all credentials are set, no need to prompt
    if nexus_url and (nexus_token or (nexus_username and nexus_password)):
        logger.info("Credentials found in environment, skipping prompt")
        return

    logger.info("Starting interactive credential setup")

    # Prompt for Nexus URL if missing
    if not nexus_url:
        logger.debug("NEXUS_URL not found, prompting user")
        print("\nNexus Configuration")
        print("-" * 40)
        nexus_url = input("Nexus URL (e.g., http://localhost:8081): ").strip()
        if not nexus_url:
            logger.error("Nexus URL is required")
            print("Error: Nexus URL is required", file=sys.stderr)
            sys.exit(1)
        os.environ["NEXUS_URL"] = nexus_url
        logger.info(f"NEXUS_URL configured: {nexus_url}")

    # Server-wide auth is optional in hosted mode -- each request carries
    # its own credentials instead (see config.py / http_auth.py) -- so
    # don't prompt for it here.
    if os.getenv("MCP_TRANSPORT", "stdio").strip().lower() == "http":
        logger.info("MCP_TRANSPORT=http: skipping server-wide credential prompt")
        print("\nConfiguration loaded\n")
        return

    # Prompt for authentication if missing
    if not nexus_token and not (nexus_username and nexus_password):
        logger.debug("Authentication not found, prompting user")
        print("\nAuthentication")
        print("-" * 40)
        print("Choose authentication method:")
        print("1. API Token (recommended)")
        print("2. Username & Password")
        choice = input("Select (1 or 2): ").strip()

        if choice == "1":
            logger.info("User selected API Token authentication")
            token = getpass("Nexus API Token: ")
            if not token:
                logger.error("API token is required")
                print("Error: API token is required", file=sys.stderr)
                sys.exit(1)
            os.environ["NEXUS_API_TOKEN"] = token
            logger.info("NEXUS_API_TOKEN configured")
        elif choice == "2":
            logger.info("User selected Username/Password authentication")
            username = input("Nexus Username: ").strip()
            password = getpass("Nexus Password: ")
            if not username or not password:
                logger.error("Username and password are required")
                print("Error: Username and password are required", file=sys.stderr)
                sys.exit(1)
            os.environ["NEXUS_USERNAME"] = username
            os.environ["NEXUS_PASSWORD"] = password
            logger.info(f"NEXUS_USERNAME configured: {username}")
        else:
            logger.error(f"Invalid authentication choice: {choice}")
            print("Error: Invalid choice", file=sys.stderr)
            sys.exit(1)

    logger.info("Configuration loaded successfully")
    print("\nConfiguration loaded\n")


async def run_http(server: NexusServer) -> None:
    """Serve `server` over Streamable HTTP (MCP_TRANSPORT=http), bound to
    MCP_HTTP_HOST/MCP_HTTP_PORT.

    Expects a TLS-terminating reverse proxy in front of this process (this
    listens on plain HTTP internally) -- see the README's "Hosted /
    Multi-user Deployment" section before exposing this beyond that proxy.
    """
    import uvicorn

    from nexus_mcp.http_app import build_http_app

    app = build_http_app(server)
    host, port = server.config.mcp_http_host, server.config.mcp_http_port
    logger.info(f"Nexus MCP Server (hosted/HTTP) listening on {host}:{port}")
    uvicorn_config = uvicorn.Config(app, host=host, port=port, log_config=None)
    await uvicorn.Server(uvicorn_config).serve()


def main():
    """Main entry point for Nexus MCP server."""
    parser = ArgumentParser(description="Sonatype Nexus OSS MCP Server")
    parser.add_argument(
        "--transport",
        default=None,
        choices=["stdio", "http"],
        help=(
            "Transport mode. 'stdio' (default): one process per user, "
            "started by the MCP client. 'http': a single, network-reachable "
            "process shared by many users, each authenticating per-request "
            "(see README). Overrides MCP_TRANSPORT if both are set."
        ),
    )
    parser.add_argument(
        "--prompt-credentials",
        action="store_true",
        help="Prompt for credentials interactively if not in .env",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    if args.transport:
        os.environ["MCP_TRANSPORT"] = args.transport

    try:
        transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
        logger.info(f"Starting Nexus MCP Server (Transport: {transport})")

        if args.prompt_credentials:
            logger.debug("Interactive credential setup requested")
            prompt_for_credentials()

        logger.info("Initializing Nexus MCP Server")
        server = NexusServer()

        logger.info("Server initialized successfully, starting event loop")
        if server.config.mcp_transport == "http":
            asyncio.run(run_http(server))
        else:
            asyncio.run(server.run())
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except (OSError, RuntimeError) as e:
        logger.exception("Runtime error")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user (Ctrl+C)")
        print("\nServer shutdown", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        logger.info("Nexus MCP Server stopped")


if __name__ == "__main__":
    main()
