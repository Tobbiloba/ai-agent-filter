# Troubleshooting Guide

Common issues and solutions when using the AI Agent Safety Filter.

## Connection Issues

### Server not starting

**Symptom:** `uvicorn server.app:app` fails to start.

**Solutions:**

1. **Check Python version:**
   ```bash
   python --version  # Should be 3.9+
   ```

2. **Activate virtual environment:**
   ```bash
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Check port availability:**
   ```bash
   # Check if port 8000 is in use
   lsof -i :8000  # Mac/Linux
   netstat -an | findstr 8000  # Windows

   # Use a different port
   uvicorn server.app:app --port 8001
   ```

### Cannot connect to server

**Symptom:** `curl: (7) Failed to connect to localhost port 8000`

**Solutions:**

1. **Verify server is running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check the correct URL:**
   - Local: `http://localhost:8000` or `http://127.0.0.1:8000`
   - Docker: Check `docker-compose.yml` for port mapping

3. **Firewall/network issues:**
   - Check if firewall blocks port 8000
   - For Docker, ensure container is running: `docker ps`

---

## Authentication Errors

### 401 Unauthorized: "Missing API key"

**Symptom:**
```json
{"detail": "Missing API key. Include it in the X-API-Key header."}
```

**Solution:** Add the `X-API-Key` header to your request:

```bash
curl -H "X-API-Key: af_your_api_key" http://localhost:8000/policies/my-project
```

Python SDK:
```python
fw = AIFirewall(api_key="af_your_api_key", ...)
```

### 403 Forbidden: "Invalid API key"

**Symptom:**
```json
{"detail": "Invalid API key or project is inactive."}
```

**Solutions:**

1. **Check API key format:** Should start with `af_`

2. **Verify key belongs to correct project:**
   ```bash
   # Each project has its own API key
   curl http://localhost:8000/projects/my-project
   ```

3. **Check if project is active:**
   - Deactivated projects reject all requests
   - Create a new project if needed

4. **API key was not saved:**
   - API keys are only shown once at creation
   - If lost, create a new project

### 403 Forbidden: "API key is for project X, not Y"

**Symptom:**
```json
{"detail": "API key is for project 'project-a', not 'project-b'."}
```

**Solution:** Use the correct API key for each project. Each project has its own unique API key.

---

## Policy Issues

### Action blocked unexpectedly

**Symptom:** An action you expected to pass is returning `"allowed": false`.

**Diagnostic steps:**

1. **Check the reason:**
   ```bash
   curl -X POST http://localhost:8000/validate_action \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_KEY" \
     -d '{"project_id": "my-project", "agent_name": "agent", "action_type": "action", "params": {}}'
   ```
   The `reason` field explains why it was blocked.

2. **View current policy:**
   ```bash
   curl http://localhost:8000/policies/my-project \
     -H "X-API-Key: YOUR_KEY"
   ```

3. **Common causes:**

   - **default is "block":** If no rules match, default applies
   - **Agent not in allowed_agents:** Check agent name spelling
   - **Constraint violation:** Check parameter values
   - **Rate limit exceeded:** Wait for window to reset

### Action allowed when it should be blocked

**Symptom:** An action that should be blocked is returning `"allowed": true`.

**Solutions:**

1. **Check action_type matches exactly:**
   ```json
   // Rule: "action_type": "pay_invoice"
   // Won't match: "payInvoice", "PAY_INVOICE", "pay-invoice"
   ```

2. **Verify constraint field names:**
   ```json
   // Correct: "params.amount"
   // Wrong: "amount", "param.amount", "params.Amount"
   ```

3. **Check constraint values:**
   ```json
   // For {"max": 1000}, value 1000 passes (it's <=, not <)
   ```

4. **Verify policy is active:**
   ```bash
   curl http://localhost:8000/policies/my-project \
     -H "X-API-Key: YOUR_KEY"
   # Check "is_active": true
   ```

### No policy found for project

**Symptom:**
```json
{"detail": "No policy found for project 'my-project'"}
```

**Solution:** Create a policy for the project:
```bash
curl -X POST http://localhost:8000/policies/my-project \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"name": "default", "version": "1.0", "default": "allow", "rules": []}'
```

**Note:** If no policy exists, actions are allowed by default.

### Rate limit hit unexpectedly

**Symptom:** `"reason": "Rate limit exceeded..."`

**Solutions:**

1. **Check rate limit configuration:**
   ```json
   {"rate_limit": {"max_requests": 100, "window_seconds": 3600}}
   // 100 requests per hour per agent per action type
   ```

2. **Rate limits are per agent AND action type:**
   - `agent_a` + `action_x` has its own counter
   - `agent_a` + `action_y` has a separate counter
   - `agent_b` + `action_x` has a separate counter

3. **Wait for window to reset** or increase the limit:
   ```json
   {"rate_limit": {"max_requests": 1000, "window_seconds": 3600}}
   ```

---

## SDK Issues

### ModuleNotFoundError: No module named 'ai_firewall'

**Solution:** Install the SDK:
```bash
pip install -e sdk/python
```

### Connection refused from SDK

**Symptom:** `ConnectionRefusedError` or timeout errors.

**Solutions:**

1. **Verify base_url:**
   ```python
   fw = AIFirewall(
       base_url="http://localhost:8000",  # Include http://
       ...
   )
   ```

2. **Check server is running:**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Docker networking:**
   - From host: `http://localhost:8000`
   - From another container: `http://host.docker.internal:8000` or service name

### SDK validation always returns allowed

**Symptom:** All actions pass even when they should be blocked.

**Solutions:**

1. **Verify project_id matches:**
   ```python
   fw = AIFirewall(
       project_id="my-project",  # Must match exactly
       ...
   )
   ```

2. **Check if policy exists:**
   - Without a policy, all actions are allowed by default

3. **Verify action_type matches policy rule:**
   ```python
   fw.execute(action_type="pay_invoice", ...)  # Must match rule exactly
   ```

---

## Validation Errors

### 422 Unprocessable Entity

**Symptom:**
```json
{
  "detail": [
    {"loc": ["body", "project_id"], "msg": "field required", "type": "value_error.missing"}
  ]
}
```

**Solutions:**

1. **Check required fields:**
   - `/projects`: `id`, `name`
   - `/validate_action`: `project_id`, `agent_name`, `action_type`
   - `/policies/{project_id}`: `rules`

2. **Verify JSON format:**
   ```bash
   # Wrong
   curl -d 'id=test'

   # Correct
   curl -H "Content-Type: application/json" -d '{"id": "test", "name": "Test"}'
   ```

3. **Check field types:**
   ```json
   // Wrong: amount as string
   {"params": {"amount": "100"}}

   // Correct: amount as number
   {"params": {"amount": 100}}
   ```

### 409 Conflict: Project already exists

**Symptom:**
```json
{"detail": "Project with ID 'my-project' already exists"}
```

**Solutions:**

1. **Use a different project ID:**
   ```bash
   curl -X POST http://localhost:8000/projects \
     -d '{"id": "my-project-2", "name": "My Project 2"}'
   ```

2. **Use the existing project:** Get its info with:
   ```bash
   curl http://localhost:8000/projects/my-project
   ```

---

## Database Issues

### Database locked (SQLite)

**Symptom:** `sqlite3.OperationalError: database is locked`

**Solutions:**

1. **Don't use SQLite in production:** Use PostgreSQL instead
   ```
   DATABASE_URL=postgresql://user:pass@host:5432/dbname
   ```

2. **Reduce concurrent connections:** SQLite doesn't handle concurrency well

3. **Check for stuck processes:**
   ```bash
   lsof ai_firewall.db  # Find processes using the file
   ```

### Database connection failed

**Symptom:** `ConnectionRefusedError` for PostgreSQL

**Solutions:**

1. **Verify DATABASE_URL:**
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   ```

2. **Check database server is running:**
   ```bash
   pg_isready -h localhost -p 5432
   ```

3. **Verify credentials and database exists**

---

## Performance Issues

### Slow response times

**Solutions:**

1. **Check database:**
   - SQLite is slow for concurrent access
   - Add indexes if using PostgreSQL

2. **Enable connection pooling:**
   - Already configured for async SQLAlchemy

3. **Check policy complexity:**
   - Many rules = longer evaluation time
   - Complex regex patterns are slow

### High memory usage

**Solutions:**

1. **Clear rate limit data:**
   - Rate limits are stored in memory
   - Restart server to clear

2. **Use external rate limiter:** Redis for distributed rate limiting (future feature)

---

## Logging and Debugging

### Enable debug mode

```bash
DEBUG=true uvicorn server.app:app --reload
```

### View blocked actions

```bash
curl "http://localhost:8000/logs/my-project?allowed=false" \
  -H "X-API-Key: YOUR_KEY"
```

### Get statistics

```bash
curl "http://localhost:8000/logs/my-project/stats" \
  -H "X-API-Key: YOUR_KEY"
```

---

## Still Stuck?

1. **Check the logs:** The server logs show detailed error information
2. **API docs:** Visit `http://localhost:8000/docs` for interactive API documentation
3. **GitHub Issues:** Report bugs at the project repository
