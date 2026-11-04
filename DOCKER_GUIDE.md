# Docker Setup Guide for Nexus MCP Server

Complete guide to running the Nexus MCP server in Docker, including local development with docker-compose.

## Quick Start

### Using docker-compose (Recommended for Development)

```bash
# Start both Nexus and Nexus MCP
docker-compose up -d

# View logs
docker-compose logs -f nexus-mcp

# Stop services
docker-compose down
```

The easiest way to get both services running together with proper networking.

### Using just the MCP Docker image

```bash
# Build the image
docker build -t nexus-mcp:latest .

# Run with API Token
docker run -d \
  --name nexus-mcp \
  -e NEXUS_URL=http://nexus.example.com:8081 \
  -e NEXUS_API_TOKEN=your-token \
  -v $(pwd)/logs:/app/logs \
  nexus-mcp:latest

# Run with Username/Password
docker run -d \
  --name nexus-mcp \
  -e NEXUS_URL=http://nexus.example.com:8081 \
  -e NEXUS_USERNAME=admin \
  -e NEXUS_PASSWORD=password \
  -v $(pwd)/logs:/app/logs \
  nexus-mcp:latest
```

## Environment Variables

### Required
- `NEXUS_URL` — Nexus server URL (e.g., `http://nexus:8081`)

### Authentication (Choose One)
- `NEXUS_API_TOKEN` — API token (recommended)
- `NEXUS_USERNAME` + `NEXUS_PASSWORD` — Username and password

### Optional
- `LOG_LEVEL` — Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- `ALLOW_INSECURE` — Allow insecure HTTP (default: `false`, set `true` for dev)

## docker-compose.yml Details

### Services

#### nexus (Sonatype Nexus Repository OSS)
- Image: `sonatype/nexus3:latest`
- Port: `8081`
- Volume: `nexus-data` (persistent storage)
- Health check: Validates API endpoint

#### nexus-mcp (Nexus MCP Server)
- Built from local `Dockerfile`
- Depends on: `nexus` service (waits for health check)
- Volume: `./logs` mounted at `/app/logs`
- Network: Connected to `nexus` service
- Resource limits: 1 CPU, 512 MB RAM

### Networks
- `nexus-network` — Custom bridge network for service communication

## Building the Docker Image

### Standard Build
```bash
docker build -t nexus-mcp:latest .
```

### Build with build args
```bash
docker build \
  --build-arg PYTHON_VERSION=3.11 \
  -t nexus-mcp:latest .
```

### Multi-stage Build Benefits
- **Stage 1 (Builder)**: Installs dependencies
- **Stage 2 (Runtime)**: Small, optimized runtime image
- Result: ~200 MB image (vs. ~500+ MB without multi-stage)

## Running with docker-compose

### Development Setup (with both services)

```bash
# Clone and navigate to project
cd nexus-mcp

# Start services
docker-compose up -d

# Wait for Nexus to be ready
docker-compose logs nexus

# Wait for MCP to start
docker-compose logs nexus-mcp

# Access Nexus UI
# http://localhost:8081
# Default credentials: admin / admin123
```

### Verify Setup

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f

# Test MCP server
docker exec nexus-mcp python -c "from nexus_mcp.server import NexusServer; print('Server OK')"

# Check logs file
docker exec nexus-mcp cat logs/nexus_mcp.log
```

### Stop Services

```bash
# Stop but keep data
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Stop specific service
docker-compose stop nexus-mcp
```

## Logging in Docker

### View Logs

```bash
# Real-time logs from MCP container
docker-compose logs -f nexus-mcp

# Nexus logs
docker-compose logs -f nexus

# Both services
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100 nexus-mcp
```

### Log Files

Logs are stored in `./logs/` directory (mounted from container):

- `logs/nexus_mcp.log` — All application logs
- `logs/nexus_mcp_error.log` — Error logs only
- Log rotation: 10 MB files, keep 5 backups

### Log Levels

Set via `LOG_LEVEL` environment variable:

| Level | Usage |
|-------|-------|
| DEBUG | Development, detailed troubleshooting |
| INFO | Normal operation (default) |
| WARNING | Potentially harmful situations |
| ERROR | Error events |
| CRITICAL | Critical errors |

## Production Deployment

### Docker Swarm

```bash
docker service create \
  --name nexus-mcp \
  --env NEXUS_URL=http://nexus:8081 \
  --env NEXUS_API_TOKEN=<token> \
  --limit-memory 512M \
  --limit-cpus 1 \
  nexus-mcp:latest
```

### Kubernetes

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nexus-mcp
spec:
  containers:
  - name: nexus-mcp
    image: nexus-mcp:latest
    env:
    - name: NEXUS_URL
      value: "http://nexus:8081"
    - name: NEXUS_API_TOKEN
      valueFrom:
        secretKeyRef:
          name: nexus-credentials
          key: api-token
    resources:
      limits:
        memory: "512Mi"
        cpu: "1"
      requests:
        memory: "256Mi"
        cpu: "500m"
    volumeMounts:
    - name: logs
      mountPath: /app/logs
  volumes:
  - name: logs
    emptyDir: {}
```

### Docker Registry

```bash
# Tag image
docker tag nexus-mcp:latest myregistry.azurecr.io/nexus-mcp:1.0.0

# Push to registry
docker push myregistry.azurecr.io/nexus-mcp:1.0.0

# Pull and run
docker run \
  -e NEXUS_URL=http://nexus:8081 \
  -e NEXUS_API_TOKEN=token \
  myregistry.azurecr.io/nexus-mcp:1.0.0
```

## Troubleshooting

### "Connection refused: nexus:8081"

**Problem:** MCP can't reach Nexus

**Solutions:**
1. Check Nexus is healthy: `docker-compose logs nexus`
2. Verify network: `docker network ls`
3. Test connectivity: `docker-compose exec nexus-mcp ping nexus`
4. Check NEXUS_URL: Should be `http://nexus:8081` (service name, not localhost)

### "Configuration error: NEXUS_URL is required"

**Problem:** Missing environment variable

**Solution:**
```bash
# Check what's set
docker-compose exec nexus-mcp env | grep NEXUS

# Update docker-compose.yml and restart
docker-compose down
docker-compose up -d
```

### "No such file or directory: /app/logs"

**Problem:** Logs directory doesn't exist

**Solution:**
```bash
# Create logs directory
mkdir -p logs

# Or let docker create it on first run
docker-compose down -v
docker-compose up -d
```

### Logs file growing too large

**Problem:** Logs taking up disk space

**Solution:**
```bash
# Clear old logs
rm logs/nexus_mcp.log.* logs/nexus_mcp_error.log.*

# Or rebuild to reset
docker-compose down -v
docker-compose up -d
```

### Performance issues

**Problem:** Container consuming too much CPU/memory

**Solutions:**
1. Check resource limits in docker-compose.yml
2. Monitor usage: `docker stats`
3. Reduce log level: `LOG_LEVEL=WARNING`
4. Check Nexus health: `docker-compose logs nexus`

## Advanced Configuration

### Custom Environment File

Create `.env.docker`:
```env
NEXUS_URL=http://nexus:8081
NEXUS_USERNAME=admin
NEXUS_PASSWORD=admin123
LOG_LEVEL=DEBUG
ALLOW_INSECURE=true
```

Use with compose:
```bash
docker-compose --env-file .env.docker up -d
```

### Persistent Logs

To keep logs across container restarts:

```yaml
# In docker-compose.yml
volumes:
  logs-data:

services:
  nexus-mcp:
    volumes:
      - logs-data:/app/logs
```

### Custom Port Mapping

```bash
# Run on different port
docker run -d \
  -p 9000:8000 \
  -e NEXUS_URL=http://nexus:8081 \
  nexus-mcp:latest
```

## Security Best Practices

✅ **Do:**
- Use non-root user (image does this by default)
- Set resource limits
- Use secrets for credentials
- Enable health checks
- Use HTTPS in production
- Keep images updated
- Regular backups

❌ **Don't:**
- Hardcode credentials in Dockerfile
- Use latest tag in production
- Run as root
- Disable HTTPS
- Mount unnecessary volumes
- Keep debug logging in production

## Docker Cleanup

```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune

# Remove unused volumes
docker volume prune

# Full cleanup (use carefully!)
docker system prune -a
```

## References

- [Docker Documentation](https://docs.docker.com/)
- [docker-compose Reference](https://docs.docker.com/compose/compose-file/)
- [Sonatype Nexus Docker](https://hub.docker.com/r/sonatype/nexus3)
- [Python Docker Best Practices](https://docs.docker.com/language/python/)
