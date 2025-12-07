# AI Firewall Python SDK

Validate AI agent actions against policies before execution.

## Installation

```bash
pip install ai-firewall
```

Or install from source:

```bash
cd sdk/python
pip install -e .
```

## Quick Start

```python
from ai_firewall import AIFirewall

# Initialize the client
fw = AIFirewall(
    api_key="af_your_api_key",
    project_id="your-project-id",
    base_url="http://localhost:8000"  # Your firewall server URL
)

# Validate an action before executing
result = fw.execute(
    agent_name="invoice_agent",
    action_type="pay_invoice",
    params={
        "vendor": "VendorA",
        "amount": 5000,
        "currency": "USD"
    }
)

if result.allowed:
    # Safe to proceed with the action
    pay_invoice(result.action_id)
else:
    # Action was blocked
    print(f"Blocked: {result.reason}")
    log_blocked_action(result.action_id, result.reason)
```

## Strict Mode

Use strict mode to automatically raise an exception when actions are blocked:

```python
fw = AIFirewall(
    api_key="af_xxx",
    project_id="my-project",
    strict=True  # Raises ActionBlockedError when blocked
)

try:
    result = fw.execute("agent", "risky_action", {"amount": 1000000})
    # This only runs if action is allowed
    do_risky_action()
except ActionBlockedError as e:
    print(f"Action {e.action_id} was blocked: {e.reason}")
```

## Policy Management

```python
# Get current policy
policy = fw.get_policy()
print(f"Policy version: {policy.version}")
print(f"Rules: {policy.rules}")

# Update policy
new_policy = fw.update_policy(
    rules=[
        {
            "action_type": "pay_invoice",
            "constraints": {
                "params.amount": {"max": 10000}
            }
        }
    ],
    version="2.0"
)
```

## Audit Logs

```python
# Get recent logs
logs = fw.get_logs(page=1, page_size=50)
for entry in logs.items:
    status = "✓" if entry.allowed else "✗"
    print(f"{status} {entry.agent_name}: {entry.action_type}")

# Filter blocked actions
blocked = fw.get_logs(allowed=False)

# Get statistics
stats = fw.get_stats()
print(f"Block rate: {stats['block_rate']}%")
```

## Context Manager

```python
with AIFirewall(api_key="...", project_id="...") as fw:
    result = fw.execute("agent", "action", {})
# Connection automatically closed
```

## Exceptions

```python
from ai_firewall import (
    AIFirewallError,       # Base exception
    AuthenticationError,   # Invalid API key
    ProjectNotFoundError,  # Project doesn't exist
    PolicyNotFoundError,   # No active policy
    ActionBlockedError,    # Action blocked (strict mode)
    NetworkError,          # Connection failed
)
```

## License

MIT
