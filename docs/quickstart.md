# Quickstart Guide

Get the AI Agent Safety Filter running in 10 minutes.

## Prerequisites

- Python 3.9+
- `pip` package manager
- `curl` (for testing)

## Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-firewall.git
cd ai-firewall

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Start the Server

```bash
uvicorn server.app:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

Verify it's running:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy", "version": "0.1.0"}
```

## Step 3: Create Your First Project

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"id": "my-first-project", "name": "My First AI Project"}'
```

Response:
```json
{
  "id": "my-first-project",
  "name": "My First AI Project",
  "api_key": "af_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789",
  "is_active": true,
  "created_at": "2025-12-09T10:00:00Z"
}
```

**Save your `api_key`** - you'll need it for all API calls and it cannot be retrieved again!

## Step 4: Create Your First Policy

Create a policy that allows payments under $1000:

```bash
curl -X POST http://localhost:8000/policies/my-first-project \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "name": "starter-policy",
    "version": "1.0",
    "default": "block",
    "rules": [
      {
        "action_type": "make_payment",
        "constraints": {
          "params.amount": {"max": 1000, "min": 0}
        }
      }
    ]
  }'
```

## Step 5: Test Action Validation

### Test an allowed action ($500 payment):

```bash
curl -X POST http://localhost:8000/validate_action \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "project_id": "my-first-project",
    "agent_name": "payment_agent",
    "action_type": "make_payment",
    "params": {"amount": 500, "vendor": "Acme Corp"}
  }'
```

Response:
```json
{
  "allowed": true,
  "action_id": "act_abc123",
  "timestamp": "2025-12-09T10:05:00Z",
  "execution_time_ms": 1
}
```

### Test a blocked action ($5000 payment):

```bash
curl -X POST http://localhost:8000/validate_action \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "project_id": "my-first-project",
    "agent_name": "payment_agent",
    "action_type": "make_payment",
    "params": {"amount": 5000, "vendor": "Acme Corp"}
  }'
```

Response:
```json
{
  "allowed": false,
  "action_id": "act_xyz789",
  "timestamp": "2025-12-09T10:06:00Z",
  "reason": "Value 5000 exceeds maximum 1000",
  "execution_time_ms": 1
}
```

## Step 6: Install the Python SDK

```bash
pip install -e sdk/python
```

## Step 7: Integrate with Your Agent

```python
from ai_firewall import AIFirewall

# Initialize the client
fw = AIFirewall(
    api_key="YOUR_API_KEY",
    project_id="my-first-project",
    base_url="http://localhost:8000"
)

# Validate before executing any action
def process_payment(vendor: str, amount: float):
    result = fw.execute(
        agent_name="payment_agent",
        action_type="make_payment",
        params={"vendor": vendor, "amount": amount}
    )

    if result.allowed:
        # Safe to proceed with payment
        print(f"Processing ${amount} payment to {vendor}")
        # ... actual payment logic here ...
        return True
    else:
        # Action blocked by policy
        print(f"Payment blocked: {result.reason}")
        return False

# Test it
process_payment("Acme Corp", 500)   # Allowed
process_payment("Acme Corp", 5000)  # Blocked
```

## Step 8: View Audit Logs

```bash
curl "http://localhost:8000/logs/my-first-project" \
  -H "X-API-Key: YOUR_API_KEY"
```

Response:
```json
{
  "items": [
    {
      "action_id": "act_xyz789",
      "agent_name": "payment_agent",
      "action_type": "make_payment",
      "params": {"amount": 5000, "vendor": "Acme Corp"},
      "allowed": false,
      "reason": "Value 5000 exceeds maximum 1000",
      "timestamp": "2025-12-09T10:06:00Z"
    },
    {
      "action_id": "act_abc123",
      "agent_name": "payment_agent",
      "action_type": "make_payment",
      "params": {"amount": 500, "vendor": "Acme Corp"},
      "allowed": true,
      "timestamp": "2025-12-09T10:05:00Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 50,
  "has_more": false
}
```

## Next Steps

1. **Expand your policy** - Add more rules, constraints, and rate limits. See [Policy Guide](policy-guide.md).

2. **Add more agents** - Use `allowed_agents` and `blocked_agents` to control which agents can perform which actions.

3. **Set up rate limiting** - Prevent abuse with `rate_limit` rules.

4. **Deploy to production** - See [Deployment Guide](../deploy/README.md) for Docker and cloud deployment options.

5. **Monitor activity** - Use `/logs/{project_id}/stats` for aggregate statistics.

## Common First Steps

### Allow multiple action types:

```json
{
  "rules": [
    {"action_type": "make_payment", "constraints": {"params.amount": {"max": 1000}}},
    {"action_type": "send_email", "constraints": {"params.to": {"pattern": ".*@company\\.com$"}}},
    {"action_type": "read_data"}
  ]
}
```

### Restrict by agent:

```json
{
  "action_type": "delete_record",
  "allowed_agents": ["admin_agent"]
}
```

### Add rate limiting:

```json
{
  "action_type": "*",
  "rate_limit": {"max_requests": 100, "window_seconds": 60}
}
```

## Need Help?

- [API Reference](api-reference.md) - Complete endpoint documentation
- [Policy Guide](policy-guide.md) - Detailed policy configuration
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [Best Practices](best-practices.md) - Policy design patterns
