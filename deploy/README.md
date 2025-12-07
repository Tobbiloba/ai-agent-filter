# Deployment Guide

This guide covers deploying the AI Agent Safety Filter to various platforms.

## Quick Start (Docker)

```bash
# Build and run locally
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

The API will be available at `http://localhost:8000`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `8000` |
| `DEBUG` | Enable debug mode | `false` |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./data/ai_firewall.db` |
| `SECRET_KEY` | Secret key for security | `change-me-in-production` |

## Platform Guides

### Railway

1. Create a new project on [Railway](https://railway.app)

2. Connect your GitHub repository

3. Add environment variables:
   ```
   SECRET_KEY=<generate-a-secure-key>
   DATABASE_URL=sqlite+aiosqlite:///./data/ai_firewall.db
   ```

4. Railway will auto-detect the Dockerfile and deploy

5. Your API will be available at `https://your-app.railway.app`

### Fly.io

1. Install the Fly CLI:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. Create `fly.toml`:
   ```toml
   app = "ai-firewall"
   primary_region = "ord"

   [build]
     dockerfile = "Dockerfile"

   [env]
     PORT = "8000"

   [http_service]
     internal_port = 8000
     force_https = true
     auto_stop_machines = true
     auto_start_machines = true

   [[vm]]
     cpu_kind = "shared"
     cpus = 1
     memory_mb = 512
   ```

3. Deploy:
   ```bash
   fly launch
   fly secrets set SECRET_KEY=<your-secret-key>
   fly deploy
   ```

### Render

1. Create a new Web Service on [Render](https://render.com)

2. Connect your repository

3. Configure:
   - **Build Command**: (leave empty, uses Dockerfile)
   - **Start Command**: (leave empty, uses Dockerfile CMD)

4. Add environment variables in the dashboard

5. Deploy

### AWS ECS / Fargate

1. Build and push to ECR:
   ```bash
   aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com

   docker build -t ai-firewall .
   docker tag ai-firewall:latest <account>.dkr.ecr.<region>.amazonaws.com/ai-firewall:latest
   docker push <account>.dkr.ecr.<region>.amazonaws.com/ai-firewall:latest
   ```

2. Create ECS task definition and service using the ECR image

### Google Cloud Run

1. Build and push to GCR:
   ```bash
   gcloud builds submit --tag gcr.io/<project>/ai-firewall
   ```

2. Deploy:
   ```bash
   gcloud run deploy ai-firewall \
     --image gcr.io/<project>/ai-firewall \
     --platform managed \
     --allow-unauthenticated \
     --set-env-vars SECRET_KEY=<your-key>
   ```

## Production Considerations

### Database

For production, consider using PostgreSQL instead of SQLite:

1. Update `docker-compose.yml` to uncomment the postgres service

2. Set environment variable:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/ai_firewall
   ```

3. Add `asyncpg` to requirements.txt

### Security

1. **Generate a strong SECRET_KEY**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Use HTTPS** in production (most platforms provide this automatically)

3. **Restrict CORS** in `server/app.py` for production:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-frontend.com"],
       ...
   )
   ```

### Monitoring

1. The `/health` endpoint returns server status
2. All actions are logged to the database
3. Use `/logs/{project_id}/stats` for metrics

### Scaling

- The server is stateless (except for SQLite)
- Rate limit counters are in-memory (reset on restart)
- For horizontal scaling, use PostgreSQL and consider Redis for rate limiting

## Testing Deployment

After deploying, test your endpoints:

```bash
# Health check
curl https://your-api.com/health

# Create a project
curl -X POST https://your-api.com/projects \
  -H "Content-Type: application/json" \
  -d '{"id": "test", "name": "Test Project"}'

# The response includes your API key
```

## Troubleshooting

### Container won't start
- Check logs: `docker-compose logs api`
- Verify environment variables are set

### Database errors
- Ensure the data volume has correct permissions
- For PostgreSQL, verify the connection string

### Health check failures
- Increase `start_period` in health check config
- Check if port 8000 is accessible
