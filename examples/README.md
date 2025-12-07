# AI Firewall Integration Examples

This directory contains example integrations showing how to use the AI Firewall SDK with popular AI agent frameworks.

## Examples

### 1. CrewAI Integration (`crewai_example.py`)

Shows multiple patterns for integrating with CrewAI:

- **Decorator Pattern**: Use `@firewall_guard` to protect functions
- **Context Manager**: Use `GuardedAction` for explicit control flow
- **Wrapper Function**: Use `guarded_execute` for simple wrapping
- **Strict Mode**: Automatically raise exceptions on blocked actions

```python
from ai_firewall import AIFirewall

fw = AIFirewall(api_key="...", project_id="...")

@firewall_guard(fw, "invoice_agent", "pay_invoice")
def pay_invoice(vendor: str, amount: float):
    # This only runs if firewall allows
    process_payment(vendor, amount)
```

### 2. OpenAI Agents Integration (`openai_agents_example.py`)

Shows how to validate OpenAI function calls before execution:

- **ProtectedToolExecutor**: Wraps tool functions with validation
- **Function Call Processing**: Validates each tool call from GPT
- **Error Handling**: Graceful handling of blocked actions

```python
executor = ProtectedToolExecutor(fw, agent_name="gpt4_assistant")
executor.register_tool("send_email", send_email_function)

# Later, when processing OpenAI function calls:
result = executor.execute(tool_name, arguments)
if "error" in result:
    # Action was blocked
    handle_blocked_action(result["reason"])
```

## Setup

1. **Start the AI Firewall server**:
   ```bash
   cd /path/to/ai-firewall
   source venv/bin/activate
   uvicorn server.app:app --reload
   ```

2. **Create a project**:
   ```bash
   curl -X POST http://localhost:8000/projects \
     -H "Content-Type: application/json" \
     -d '{"id": "my-project", "name": "My Project"}'
   ```
   Save the returned `api_key`.

3. **Create a policy**:
   ```bash
   curl -X POST http://localhost:8000/policies/my-project \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{
       "name": "default",
       "version": "1.0",
       "default": "allow",
       "rules": [
         {
           "action_type": "pay_invoice",
           "constraints": {
             "params.amount": {"max": 10000}
           }
         },
         {
           "action_type": "execute_sql",
           "blocked_agents": ["*"]
         }
       ]
     }'
   ```

4. **Install the SDK**:
   ```bash
   pip install -e sdk/python
   ```

5. **Run examples**:
   ```bash
   # Update API key in the example files first
   python examples/crewai_example.py
   python examples/openai_agents_example.py
   ```

## Policy Examples

### Allow payments up to $10,000
```json
{
  "action_type": "pay_invoice",
  "constraints": {
    "params.amount": {"max": 10000, "min": 0},
    "params.currency": {"in": ["USD", "EUR"]}
  }
}
```

### Block all SQL execution
```json
{
  "action_type": "execute_sql",
  "blocked_agents": ["*"]
}
```

### Rate limit API calls
```json
{
  "action_type": "api_call",
  "rate_limit": {
    "max_requests": 100,
    "window_seconds": 3600
  }
}
```

### Only allow internal emails
```json
{
  "action_type": "send_email",
  "constraints": {
    "params.to": {"pattern": ".*@company\\.com$"}
  }
}
```

## Best Practices

1. **Fail Closed**: Use `default: "block"` in production policies
2. **Log Everything**: All actions are logged regardless of allow/block
3. **Use Strict Mode**: In critical paths, use `strict=True` to raise exceptions
4. **Version Policies**: Increment version when updating policies
5. **Test Policies**: Test both allowed and blocked scenarios before deployment
