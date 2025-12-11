# AI Agent Safety Filter

A lightweight middleware that intercepts AI agent actions, validates them against policy rules, and logs all activity.

**🛡️ Control what your AI agents can do before they do it.**

## Features

- **Action Validation**: Validate agent actions against configurable policies before execution
- **Policy-as-Code**: Define rules for parameter constraints, rate limits, and agent permissions
- **Audit Logging**: Complete audit trail of all allowed and blocked actions
- **Multi-Language SDKs**: Python and Node.js/TypeScript SDKs for easy integration
- **Framework Agnostic**: Works with CrewAI, LangChain, OpenAI Agents, Vercel AI SDK, and more
- **Fast**: Sub-millisecond validation latency

## Quick Start

### 1. Start the Server

```bash
# Clone and setup
git clone https://github.com/yourusername/ai-firewall.git
cd ai-firewall

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn server.app:app --reload
```

The API is now running at `http://localhost:8000`. See docs at `http://localhost:8000/docs`.

### 2. Create a Project

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"id": "my-project", "name": "My AI Project"}'
```

Save the returned `api_key` - you'll need it for all API calls.

### 3. Define a Policy

```bash
curl -X POST http://localhost:8000/policies/my-project \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "name": "production",
    "version": "1.0",
    "default": "allow",
    "rules": [
      {
        "action_type": "pay_invoice",
        "constraints": {
          "params.amount": {"max": 10000, "min": 0},
          "params.currency": {"in": ["USD", "EUR"]}
        }
      }
    ]
  }'
```

### 4. Install the SDK

#### Python

```bash
pip install -e sdk/python
```

#### Node.js / TypeScript

```bash
npm install @ai-agent-filter/sdk
```

### 5. Protect Your Agent

#### Python

```python
from ai_firewall import AIFirewall

fw = AIFirewall(
    api_key="YOUR_API_KEY",
    project_id="my-project",
    base_url="http://localhost:8000"
)

# Before executing any agent action:
result = fw.execute(
    agent_name="invoice_agent",
    action_type="pay_invoice",
    params={"vendor": "Acme", "amount": 5000, "currency": "USD"}
)

if result.allowed:
    # Safe to proceed
    execute_payment(...)
else:
    # Action blocked
    print(f"Blocked: {result.reason}")
```

#### Node.js / TypeScript

```typescript
import { AIFirewall } from '@ai-agent-filter/sdk';

const fw = new AIFirewall({
  apiKey: 'YOUR_API_KEY',
  projectId: 'my-project',
  baseUrl: 'http://localhost:8000',
});

// Before executing any agent action:
const result = await fw.execute('invoice_agent', 'pay_invoice', {
  vendor: 'Acme',
  amount: 5000,
  currency: 'USD',
});

if (result.allowed) {
  // Safe to proceed
  await executePayment();
} else {
  // Action blocked
  console.log(`Blocked: ${result.reason}`);
}
```

## Policy Rules

### Parameter Constraints

```json
{
  "action_type": "pay_invoice",
  "constraints": {
    "params.amount": {"max": 10000, "min": 0},
    "params.currency": {"in": ["USD", "EUR"]},
    "params.vendor": {"not_in": ["BlockedVendor"]},
    "params.email": {"pattern": ".*@company\\.com$"}
  }
}
```

### Agent Restrictions

```json
{
  "action_type": "delete_record",
  "allowed_agents": ["admin_agent"],
  "blocked_agents": ["untrusted_agent"]
}
```

### Rate Limiting

```json
{
  "action_type": "api_call",
  "rate_limit": {
    "max_requests": 100,
    "window_seconds": 3600
  }
}
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/validate_action` | Validate an action |
| `POST` | `/projects` | Create a new project |
| `GET` | `/projects/{id}` | Get project info |
| `POST` | `/policies/{project_id}` | Create/update policy |
| `GET` | `/policies/{project_id}` | Get active policy |
| `GET` | `/logs/{project_id}` | Get audit logs |
| `GET` | `/logs/{project_id}/stats` | Get log statistics |

## SDKs

| Language | Package | Documentation |
|----------|---------|---------------|
| Python | `pip install ai-firewall` | [sdk/python/README.md](sdk/python/README.md) |
| Node.js/TypeScript | `npm install @ai-agent-filter/sdk` | [sdk/nodejs/README.md](sdk/nodejs/README.md) |

## Integration Examples

See the `examples/` directory for integration patterns:

### Python
- **CrewAI**: Decorator, context manager, and wrapper patterns
- **OpenAI Agents**: Protected tool executor for function calling

### Node.js / TypeScript
- **LangChain.js**: Tool wrapper with `withFirewall()` higher-order function
- **Vercel AI SDK**: Tool integration with validation
- **Express.js**: Middleware for protecting API endpoints
- **Next.js**: Route handler and server action protection

## Deployment

### Docker

```bash
docker-compose up -d
```

### Cloud Platforms

See `deploy/README.md` for guides on:
- Railway
- Fly.io
- Render
- AWS ECS
- Google Cloud Run

## Project Structure

```
ai-firewall/
├── server/           # FastAPI server
│   ├── app.py        # Main application
│   ├── routes/       # API endpoints
│   ├── models/       # Database models
│   ├── services/     # Business logic
│   └── schemas/      # Pydantic schemas
├── sdk/
│   ├── python/       # Python SDK
│   └── nodejs/       # Node.js/TypeScript SDK
├── examples/         # Integration examples
├── deploy/           # Deployment guides
├── Dockerfile
└── docker-compose.yml
```

## Configuration

Environment variables (see `.env.example` for full list):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection | `sqlite+aiosqlite:///./ai_firewall.db` |
| `SECRET_KEY` | Security key | `change-me-in-production` |
| `DEBUG` | Enable debug mode | `false` |
| `REDIS_URL` | Redis URL for caching (optional) | `` (disabled) |
| `FAIL_CLOSED` | Block actions on service errors | `false` |

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run tests
pytest

# Format code
black server/ sdk/
ruff check server/ sdk/
```

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

Built for the age of AI agents. 🤖
