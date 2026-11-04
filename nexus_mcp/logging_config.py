import logging
import logging.handlers
import os
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging for the Nexus MCP server.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Get log level from environment or argument
    env_log_level = os.getenv("LOG_LEVEL", log_level).upper()
    numeric_level = getattr(logging, env_log_level, logging.INFO)

    # Create logger
    logger = logging.getLogger("nexus_mcp")
    logger.setLevel(numeric_level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Log format with timestamp, level, and message
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # stdout carries the MCP JSON-RPC protocol.  Send diagnostics to stderr so
    # they neither corrupt protocol messages nor target the stream closed by
    # the stdio transport during shutdown.
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # File handler (all levels)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "nexus_mcp.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,  # Keep 5 backup files
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    # Error file handler (ERROR and above)
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "nexus_mcp_error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    logger.addHandler(error_handler)

    # Log startup info
    logger.info("=" * 60)
    logger.info("Nexus MCP Server Starting")
    logger.info(f"Log Level: {env_log_level}")
    logger.info(f"Log Directory: {log_dir.absolute()}")
    logger.info("=" * 60)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f"nexus_mcp.{name}")
