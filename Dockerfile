# Multi-stage build for Nexus MCP Server

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
# LICENSE must be present here -- pyproject.toml declares
# `license = { file = "LICENSE" }`, and hatchling's build-time metadata
# validation fails without it (even for an editable install).
COPY pyproject.toml LICENSE ./
COPY nexus_mcp/ ./nexus_mcp/
COPY nexus/ ./nexus/

# Install dependencies
RUN pip install --no-cache-dir --user -e .

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 nexus && \
    mkdir -p /app/logs && \
    chown -R nexus:nexus /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/nexus/.local

# Copy application code
COPY --chown=nexus:nexus nexus_mcp/ ./nexus_mcp/
COPY --chown=nexus:nexus nexus/ ./nexus/

# Set environment variables
ENV PATH=/home/nexus/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO

# Switch to non-root user
USER nexus

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Only relevant when MCP_TRANSPORT=http (see README's "Hosted / Multi-user
# Deployment" section) -- ignored for the default stdio transport, so this
# doesn't change anything for existing per-user WSL/Docker deployments.
EXPOSE 8000

# Defaults to stdio (one container per user, credentials from env vars --
# unchanged). Override with `-e MCP_TRANSPORT=http` (and don't set
# NEXUS_USERNAME/PASSWORD/API_TOKEN) to run this same image as a shared,
# multi-user hosted server instead; put a TLS-terminating reverse proxy in
# front of it.
CMD ["nexus-mcp"]
