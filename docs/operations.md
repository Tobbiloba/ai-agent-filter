# Operations Guide

Production deployment, monitoring, backups, and configuration reference.

## Table of Contents

- [Health Monitoring](#health-monitoring)
- [Logging & Audit Trails](#logging--audit-trails)
- [Database Management](#database-management)
- [Environment Variables](#environment-variables)
- [Production Checklist](#production-checklist)

---

## Health Monitoring

### Health Check Endpoint

The `/health` endpoint returns the service status:

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Uptime Monitoring

Integrate with monitoring services using the health endpoint:

**Uptime Robot / Pingdom:**
- URL: `https://your-domain.com/health`
- Check interval: 1-5 minutes
- Alert on: non-200 response or timeout

**Docker Healthcheck (built-in):**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**Kubernetes Liveness Probe:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
```

### Metrics to Monitor

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| API response time | Load balancer / APM | > 100ms p95 |
| Error rate (4xx/5xx) | Access logs | > 1% |
| Block rate | `/logs/{project}/stats` | Sudden spike |
| Database size | File system | > 1GB (SQLite) |

---

## Logging & Audit Trails

### Built-in Audit Logging

All action validations are logged to the database automatically:

```bash
# Get recent logs
curl "http://localhost:8000/logs/{project_id}" \
  -H "X-API-Key: YOUR_KEY"

# Get blocked actions only
curl "http://localhost:8000/logs/{project_id}?allowed=false" \
  -H "X-API-Key: YOUR_KEY"

# Get statistics
curl "http://localhost:8000/logs/{project_id}/stats" \
  -H "X-API-Key: YOUR_KEY"
```

### Log Entry Fields

Each audit log entry contains:

| Field | Description |
|-------|-------------|
| `action_id` | Unique ID (act_xxx) |
| `project_id` | Project identifier |
| `agent_name` | Agent that performed action |
| `action_type` | Type of action attempted |
| `params` | Action parameters (JSON) |
| `allowed` | Whether action was allowed |
| `reason` | Block reason (if blocked) |
| `policy_version` | Policy version used |
| `execution_time_ms` | Validation latency |
| `timestamp` | ISO 8601 timestamp |

### Application Logs

The server outputs logs to stdout. Capture with your container runtime:

**Docker:**
```bash
docker logs ai-firewall-api -f
```

**Docker Compose:**
```bash
docker-compose logs -f api
```

### External Logging Services

For production, forward logs to a centralized service:

**Datadog:**
```yaml
# docker-compose.yml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    labels:
      com.datadoghq.ad.logs: '[{"source": "python", "service": "ai-firewall"}]'
```

**AWS CloudWatch:**
```yaml
logging:
  driver: awslogs
  options:
    awslogs-group: ai-firewall
    awslogs-region: us-east-1
    awslogs-stream-prefix: api
```

**Promtail/Loki:**
```yaml
# promtail config
scrape_configs:
  - job_name: ai-firewall
    static_configs:
      - targets:
          - localhost
        labels:
          job: ai-firewall
          __path__: /var/log/ai-firewall/*.log
```

---

## Database Management

### SQLite (Development/Small Scale)

Default database location: `./ai_firewall.db`

#### Backup Strategy

**Manual Backup:**
```bash
# Stop the server or use SQLite backup API
sqlite3 ai_firewall.db ".backup 'backup_$(date +%Y%m%d_%H%M%S).db'"
```

**Automated Daily Backup (cron):**
```bash
# Add to crontab -e
0 2 * * * cd /path/to/app && sqlite3 ai_firewall.db ".backup '/backups/ai_firewall_$(date +\%Y\%m\%d).db'"
```

**Docker Volume Backup:**
```bash
# Backup the data volume
docker run --rm -v firewall-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/firewall-backup-$(date +%Y%m%d).tar.gz /data
```

#### Restore from Backup

```bash
# Stop the server
docker-compose down

# Replace database file
cp backup_20250101.db ai_firewall.db

# Restart
docker-compose up -d
```

#### SQLite Limitations

- Single-writer concurrency
- Not recommended for > 100 req/s
- Max practical size: ~1GB

### PostgreSQL (Production)

For production workloads, use PostgreSQL:

**1. Update environment:**
```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ai_firewall
```

**2. Docker Compose with PostgreSQL:**
```yaml
services:
  api:
    environment:
      DATABASE_URL: postgresql+asyncpg://firewall:secret@db:5432/firewall

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: firewall
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: firewall
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  postgres-data:
```

#### PostgreSQL Backup

**pg_dump:**
```bash
pg_dump -h localhost -U firewall -d firewall > backup_$(date +%Y%m%d).sql
```

**Automated with cron:**
```bash
0 2 * * * pg_dump -h localhost -U firewall firewall | gzip > /backups/firewall_$(date +\%Y\%m\%d).sql.gz
```

**Restore:**
```bash
psql -h localhost -U firewall -d firewall < backup_20250101.sql
```

### Data Retention

Audit logs can grow large. Consider periodic cleanup:

```sql
-- Delete logs older than 90 days
DELETE FROM audit_logs
WHERE timestamp < datetime('now', '-90 days');

-- Vacuum to reclaim space (SQLite)
VACUUM;
```

---

## Environment Variables

### Complete Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Enable debug mode (verbose errors) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./ai_firewall.db` | Database connection string |
| `SECRET_KEY` | `change-me-in-production` | Secret for cryptographic operations |
| `API_KEY_HEADER` | `X-API-Key` | Header name for API key authentication |
| `RATE_LIMIT_REQUESTS` | `100` | Default rate limit (requests per window) |
| `RATE_LIMIT_WINDOW` | `3600` | Rate limit window in seconds |

### Configuration Details

#### HOST
```bash
HOST=0.0.0.0      # Listen on all interfaces (default)
HOST=127.0.0.1    # Localhost only
```

#### PORT
```bash
PORT=8000         # Default
PORT=80           # Standard HTTP (requires root or capabilities)
PORT=443          # HTTPS (use with reverse proxy)
```

#### DEBUG
```bash
DEBUG=false       # Production (sanitized errors)
DEBUG=true        # Development (detailed stack traces)
```

**Warning:** Never enable DEBUG in production - it exposes internal details.

#### DATABASE_URL

**SQLite:**
```bash
DATABASE_URL=sqlite+aiosqlite:///./ai_firewall.db      # Relative path
DATABASE_URL=sqlite+aiosqlite:////data/ai_firewall.db  # Absolute path
```

**PostgreSQL:**
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname?ssl=require
```

#### SECRET_KEY

Generate a secure key for production:

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32
```

**Example:**
```bash
SECRET_KEY=Ks8jF2nL9pQr4tWx6zA1bC3dE5fG7hI8
```

#### Rate Limiting

```bash
RATE_LIMIT_REQUESTS=100    # Max requests per window
RATE_LIMIT_WINDOW=3600     # Window size in seconds (1 hour)
```

**Examples:**
- 100 req/hour: `RATE_LIMIT_REQUESTS=100`, `RATE_LIMIT_WINDOW=3600`
- 10 req/minute: `RATE_LIMIT_REQUESTS=10`, `RATE_LIMIT_WINDOW=60`
- 1000 req/day: `RATE_LIMIT_REQUESTS=1000`, `RATE_LIMIT_WINDOW=86400`

Note: Policy-level rate limits override these defaults.

### Example .env Files

**Development:**
```bash
HOST=127.0.0.1
PORT=8000
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./ai_firewall.db
SECRET_KEY=dev-secret-not-for-production
```

**Production:**
```bash
HOST=0.0.0.0
PORT=8000
DEBUG=false
DATABASE_URL=postgresql+asyncpg://firewall:SECURE_PASSWORD@db:5432/firewall
SECRET_KEY=Ks8jF2nL9pQr4tWx6zA1bC3dE5fG7hI8jK0lM2nO4pQ6rS8t
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=3600
```

---

## Production Checklist

### Before Going Live

- [ ] **SECRET_KEY** - Generate unique, secure key
- [ ] **DEBUG=false** - Disable debug mode
- [ ] **DATABASE_URL** - Use PostgreSQL for production
- [ ] **HTTPS** - Enable TLS via reverse proxy
- [ ] **Backups** - Configure automated backups
- [ ] **Monitoring** - Set up health checks and alerts

### Security Hardening

- [ ] Run as non-root user (Docker image does this by default)
- [ ] Use secrets manager for credentials (AWS Secrets Manager, Vault)
- [ ] Enable rate limiting at load balancer level
- [ ] Set up WAF rules if exposed to internet
- [ ] Rotate API keys periodically
- [ ] Review audit logs for anomalies

### Scaling Considerations

**Horizontal Scaling:**
- The API is stateless - run multiple instances behind load balancer
- Rate limits are in-memory per instance (use Redis for distributed rate limiting)
- Database is the bottleneck - use PostgreSQL with connection pooling

**Recommended Architecture:**
```
                    ┌─────────────┐
                    │ Load Balancer│
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
      ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
      │ API #1  │    │ API #2  │    │ API #3  │
      └────┬────┘    └────┬────┘    └────┬────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────▼──────┐
                    │ PostgreSQL  │
                    └─────────────┘
```

### Disaster Recovery

1. **Regular backups** - Daily database backups retained for 30 days
2. **Backup testing** - Monthly restore test to verify backups work
3. **Runbook** - Document recovery procedures
4. **RTO/RPO** - Define acceptable downtime and data loss limits

---

## Further Reading

- [Quickstart Guide](quickstart.md) - Get started in 10 minutes
- [Deployment Guide](../deploy/README.md) - Cloud platform deployments
- [API Reference](api-reference.md) - Complete endpoint documentation
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
