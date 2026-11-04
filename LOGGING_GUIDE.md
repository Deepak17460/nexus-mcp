# Logging System Guide

Complete documentation of the Nexus MCP server's logging system.

## Overview

The Nexus MCP server uses Python's built-in `logging` module with multiple handlers for comprehensive log capture and analysis.

## Log Files

### Primary Log File
**Location:** `logs/nexus_mcp.log`

**Content:** All application logs
- Configuration startup
- Authentication details (username, not password)
- Tool execution traces
- Error conditions

**Rotation:**
- Max size: 10 MB
- Backup count: 5 files
- Automatic rotation when size exceeded

### Error Log File
**Location:** `logs/nexus_mcp_error.log`

**Content:** ERROR and CRITICAL level logs only

**Rotation:**
- Max size: 10 MB
- Backup count: 3 files
- Separate file for error analysis

### Console Output
Logs are also printed to console (stdout/stderr) at or above the configured level.

## Log Levels

| Level | Severity | Use Case |
|-------|----------|----------|
| DEBUG | Low | Detailed diagnostics, variable values, function calls |
| INFO | Low | Normal operation, configuration, startup |
| WARNING | Medium | Unusual but recoverable, deprecations |
| ERROR | High | Error conditions that don't stop the server |
| CRITICAL | Critical | System-level failures, unrecoverable errors |

## Configuration

### Environment Variable

```bash
# Set log level (default: INFO)
export LOG_LEVEL=DEBUG
nexus-mcp

# Or in .env
LOG_LEVEL=DEBUG
```

### Command Line

```bash
nexus-mcp --log-level DEBUG
```

### Log Directory

Logs are automatically created in `logs/` directory:

```
logs/
├── nexus_mcp.log              # Main log file
├── nexus_mcp.log.1            # Rotated backups
├── nexus_mcp.log.2
├── ...
└── nexus_mcp_error.log        # Error-only log
```

## Log Format

All logs follow this format:

```
TIMESTAMP - LOGGER - LEVEL - [FILE:LINE] - MESSAGE
```

**Example:**
```
2024-01-15 10:23:45 - nexus_mcp.server - INFO - [server.py:42] - Health check completed successfully
2024-01-15 10:23:46 - nexus_mcp.config - DEBUG - [config.py:58] - NEXUS_URL set to: http://localhost:8081
2024-01-15 10:23:47 - nexus_mcp.main - ERROR - [main.py:125] - Configuration error: Authentication failed
```

**Components:**
- `TIMESTAMP` — ISO format with seconds
- `LOGGER` — Module name (nexus_mcp.*)
- `LEVEL` — Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `FILE:LINE` — Source code location
- `MESSAGE` — Log message

## Docker Logging

### View Logs

```bash
# Real-time logs
docker-compose logs -f nexus-mcp

# Last 100 lines
docker-compose logs --tail=100 nexus-mcp

# With timestamps
docker-compose logs -f --timestamps nexus-mcp
```

### Log Level in Docker

Set via environment variable in docker-compose.yml:

```yaml
services:
  nexus-mcp:
    environment:
      LOG_LEVEL: DEBUG
```

Or use .env file:

```bash
docker-compose --env-file .env.docker up -d
```

## Analyzing Logs

### Find Errors

```bash
# All errors in main log
grep ERROR logs/nexus_mcp.log

# All critical errors
grep CRITICAL logs/nexus_mcp.log

# Error file (only has errors)
cat logs/nexus_mcp_error.log
```

### Track Specific Operation

```bash
# Find all logs from a specific module
grep "nexus_mcp.server" logs/nexus_mcp.log

# Find logs in a time range
grep "2024-01-15 10:" logs/nexus_mcp.log

# Follow logs in real-time
tail -f logs/nexus_mcp.log
```

### Count Log Entries

```bash
# Count by level
grep -c "INFO" logs/nexus_mcp.log
grep -c "ERROR" logs/nexus_mcp.log

# Count all entries
wc -l logs/nexus_mcp.log
```

## Log Examples

### Startup (INFO Level)

```
2024-01-15 10:00:00 - nexus_mcp - INFO - [logging_config.py:40] - ============================================================
2024-01-15 10:00:00 - nexus_mcp - INFO - [logging_config.py:41] - Nexus MCP Server Starting
2024-01-15 10:00:00 - nexus_mcp - INFO - [logging_config.py:42] - Log Level: INFO
2024-01-15 10:00:00 - nexus_mcp - INFO - [logging_config.py:43] - Log Directory: /app/logs
2024-01-15 10:00:00 - nexus_mcp - INFO - [logging_config.py:44] - ============================================================
2024-01-15 10:00:00 - nexus_mcp.main - INFO - [main.py:89] - Starting Nexus MCP Server (Transport: stdio)
2024-01-15 10:00:00 - nexus_mcp.main - INFO - [main.py:93] - Initializing Nexus MCP Server
2024-01-15 10:00:00 - nexus_mcp.config - INFO - [config.py:25] - Using API Token authentication
2024-01-15 10:00:00 - nexus_mcp.main - INFO - [main.py:97] - Server initialized successfully, starting event loop
```

### Configuration Validation (DEBUG Level)

```
2024-01-15 10:00:01 - nexus_mcp.config - DEBUG - [config.py:45] - Validating configuration
2024-01-15 10:00:01 - nexus_mcp.config - DEBUG - [config.py:49] - NEXUS_URL set to: http://localhost:8081
2024-01-15 10:00:01 - nexus_mcp.config - INFO - [config.py:66] - Using API Token authentication
```

### Error Handling (ERROR Level)

```
2024-01-15 10:05:30 - nexus_mcp.config - ERROR - [config.py:48] - NEXUS_URL environment variable is missing
2024-01-15 10:05:30 - nexus_mcp.main - ERROR - [main.py:102] - Configuration error: NEXUS_URL is required
```

### Security Warnings (WARNING Level)

```
2024-01-15 10:00:02 - nexus_mcp.config - WARNING - [config.py:54] - Using insecure HTTP connection (ALLOW_INSECURE=true)
```

## Performance Considerations

### Log Rotation

Files are rotated automatically when they exceed 10 MB:

```
nexus_mcp.log        (current, ~0-10 MB)
nexus_mcp.log.1      (previous rotation)
nexus_mcp.log.2      (older)
...
nexus_mcp.log.5      (oldest kept)
```

Old rotated files beyond the backup count are deleted.

### Disk Space

Estimate log file growth:

- **INFO level**: ~50-100 KB/day of normal operation
- **DEBUG level**: ~1-5 MB/day (verbose)
- **With 5 backups**: ~10 MB max for main log

### Optimization

**For Production:**
```bash
# Use WARNING or ERROR level
LOG_LEVEL=WARNING

# Reduces log volume and disk usage
```

**For Troubleshooting:**
```bash
# Use DEBUG level temporarily
LOG_LEVEL=DEBUG

# Monitor disk space while debugging
```

## Credential Security

### What's Logged

✅ **Logged (safe):**
- Configuration file paths
- Nexus URL
- Authentication method (token or username)
- Username (not password)
- HTTP method and endpoint
- Response status codes
- Validation errors

❌ **Never Logged (secure):**
- API tokens
- Passwords
- Authorization headers
- Request/response bodies with sensitive data
- Connection strings with credentials

### Example Safe Logs

```
2024-01-15 10:00:00 - nexus_mcp.config - INFO - [config.py:66] - Using API Token authentication
2024-01-15 10:00:00 - nexus_mcp.config - INFO - [config.py:68] - NEXUS_USERNAME configured: admin
```

Notice: No actual token or password is logged.

## Integration with Monitoring

### ELK Stack (Elasticsearch, Logstash, Kibana)

```yaml
# logstash.conf
input {
  file {
    path => "/var/log/nexus_mcp/nexus_mcp.log"
    start_position => "beginning"
  }
}

filter {
  grok {
    match => { "message" => "%{TIMESTAMP_ISO8601:timestamp} - %{DATA:logger} - %{LOGLEVEL:level} - \[%{DATA:source}\] - %{GREEDYDATA:msg}" }
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "nexus-mcp-%{+YYYY.MM.dd}"
  }
}
```

### Syslog Integration

```bash
# Send logs to syslog (Linux/macOS)
tail -f logs/nexus_mcp.log | logger -t nexus-mcp
```

### Datadog Integration

```python
# Add to logging_config.py
from datadog import initialize, api

options = {
    'api_key': os.getenv('DATADOG_API_KEY'),
    'app_key': os.getenv('DATADOG_APP_KEY')
}
initialize(**options)

# Use DatadogHandler
```

## Troubleshooting Log Issues

### "Permission denied: logs/nexus_mcp.log"

```bash
# Fix permissions
chmod 755 logs/
chmod 644 logs/*.log
```

### Logs not appearing

```bash
# Check log level
export LOG_LEVEL=DEBUG

# Check directory exists
mkdir -p logs

# Check write permissions
ls -la logs/
```

### Logs growing too fast

```bash
# Lower log level
LOG_LEVEL=WARNING

# Check for errors causing verbose logging
grep ERROR logs/nexus_mcp.log | wc -l
```

### Old logs not being deleted

```bash
# Manual cleanup
rm logs/nexus_mcp.log.[0-9]

# Or use script
find logs/ -type f -mtime +30 -delete
```

## Best Practices

✅ **Do:**
- Use appropriate log levels for each situation
- Check logs when troubleshooting
- Rotate logs in production
- Secure log files containing any sensitive data
- Monitor log directory disk space
- Use DEBUG level only during development

❌ **Don't:**
- Log credentials or tokens
- Create too many log files
- Ignore error logs
- Mix log formats
- Delete logs without archiving
- Use DEBUG level in production

## References

- [Python logging documentation](https://docs.python.org/3/library/logging.html)
- [Logging best practices](https://docs.python.org/3/howto/logging.html)
- [Log rotation documentation](https://docs.python.org/3/library/logging.handlers.html#rotatingfilehandler)
