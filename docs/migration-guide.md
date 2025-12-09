# Migration Guide

How to add the AI Agent Safety Filter to your existing AI agent system.

## Overview

The AI Agent Safety Filter acts as a middleware layer between your agent and its actions. Migration involves:

1. Setting up the filter service
2. Wrapping your agent's action execution
3. Defining policies
4. Testing in shadow mode

## Migration Strategies

### Strategy 1: Shadow Mode (Recommended)

Start by logging actions without blocking. This lets you:
- See what actions your agents perform
- Design policies based on real data
- Validate policies before enforcement

```python
from ai_firewall import AIFirewall

fw = AIFirewall(api_key="...", project_id="...")

def execute_action(agent_name, action_type, params):
    # Validate but don't block (shadow mode)
    result = fw.execute(agent_name, action_type, params)

    if not result.allowed:
        # Log but continue
        logger.warning(f"Would block: {action_type} - {result.reason}")

    # Always execute (shadow mode)
    return original_execute(action_type, params)
```

After 1-2 weeks of data collection, analyze blocked actions and refine your policy.

### Strategy 2: Gradual Enforcement

Start with permissive policies and tighten over time:

```json
// Week 1: Log everything, block nothing
{"default": "allow", "rules": []}

// Week 2: Block obviously dangerous actions
{
  "default": "allow",
  "rules": [
    {"action_type": "delete_all_data", "blocked_agents": ["*"]}
  ]
}

// Week 3: Add constraints
{
  "default": "allow",
  "rules": [
    {"action_type": "delete_all_data", "blocked_agents": ["*"]},
    {"action_type": "transfer_funds", "constraints": {"params.amount": {"max": 10000}}}
  ]
}

// Week 4: Switch to default block
{
  "default": "block",
  "rules": [
    {"action_type": "safe_action_1"},
    {"action_type": "safe_action_2"},
    ...
  ]
}
```

### Strategy 3: Per-Agent Migration

Migrate agents one at a time:

```python
MIGRATED_AGENTS = {"invoice_agent", "email_agent"}

def execute_action(agent_name, action_type, params):
    if agent_name in MIGRATED_AGENTS:
        result = fw.execute(agent_name, action_type, params)
        if not result.allowed:
            raise ActionBlockedError(result.reason)

    return original_execute(action_type, params)
```

---

## Framework-Specific Migration

### CrewAI

**Before:**
```python
from crewai import Agent, Task, Crew

agent = Agent(
    role="Financial Analyst",
    tools=[pay_invoice, send_email]
)
```

**After (Decorator Pattern):**
```python
from ai_firewall import AIFirewall

fw = AIFirewall(api_key="...", project_id="...")

def protected(agent_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = fw.execute(
                agent_name=agent_name,
                action_type=func.__name__,
                params=kwargs
            )
            if not result.allowed:
                return f"Action blocked: {result.reason}"
            return func(*args, **kwargs)
        return wrapper
    return decorator

@protected("finance_agent")
def pay_invoice(vendor: str, amount: float):
    # Original implementation
    ...
```

**After (Context Manager Pattern):**
```python
from ai_firewall import AIFirewall

fw = AIFirewall(api_key="...", project_id="...")

def execute_tool(agent_name: str, tool_name: str, params: dict):
    result = fw.execute(agent_name, tool_name, params)
    if not result.allowed:
        raise Exception(f"Blocked: {result.reason}")

    # Execute the actual tool
    return tools[tool_name](**params)
```

### LangChain

**Before:**
```python
from langchain.agents import Tool

tools = [
    Tool(name="pay_invoice", func=pay_invoice, description="..."),
]
```

**After:**
```python
from ai_firewall import AIFirewall

fw = AIFirewall(api_key="...", project_id="...")

def wrap_tool(tool_func, tool_name, agent_name="langchain_agent"):
    def wrapped(*args, **kwargs):
        result = fw.execute(agent_name, tool_name, kwargs)
        if not result.allowed:
            return f"Action blocked by policy: {result.reason}"
        return tool_func(*args, **kwargs)
    return wrapped

tools = [
    Tool(
        name="pay_invoice",
        func=wrap_tool(pay_invoice, "pay_invoice"),
        description="..."
    ),
]
```

### OpenAI Function Calling

**Before:**
```python
def execute_function(name: str, arguments: dict):
    return functions[name](**arguments)
```

**After:**
```python
from ai_firewall import AIFirewall

fw = AIFirewall(api_key="...", project_id="...")

def execute_function(name: str, arguments: dict, agent_name="openai_agent"):
    result = fw.execute(agent_name, name, arguments)
    if not result.allowed:
        return {"error": result.reason, "blocked": True}

    return functions[name](**arguments)
```

### Custom Agent Frameworks

**Generic wrapper pattern:**
```python
from ai_firewall import AIFirewall

class SafetyWrapper:
    def __init__(self, api_key: str, project_id: str, base_url: str = "http://localhost:8000"):
        self.fw = AIFirewall(api_key=api_key, project_id=project_id, base_url=base_url)

    def execute(self, agent_name: str, action_type: str, params: dict, executor):
        """
        Wrap any action executor with safety validation.

        Args:
            agent_name: Name of the agent
            action_type: Type of action being performed
            params: Action parameters
            executor: Callable that performs the actual action

        Returns:
            Action result or raises exception if blocked
        """
        result = self.fw.execute(agent_name, action_type, params)

        if not result.allowed:
            raise PermissionError(f"Action blocked: {result.reason}")

        return executor()

# Usage
safety = SafetyWrapper(api_key="...", project_id="...")

def my_agent_action():
    action_type = "transfer_funds"
    params = {"amount": 5000, "recipient": "vendor@example.com"}

    return safety.execute(
        agent_name="my_agent",
        action_type=action_type,
        params=params,
        executor=lambda: actual_transfer(params)
    )
```

---

## Mapping Your Actions

### Inventory Your Actions

List all actions your agents can perform:

| Agent | Action | Parameters | Risk Level |
|-------|--------|------------|------------|
| invoice_agent | pay_invoice | amount, vendor, currency | High |
| invoice_agent | read_invoice | invoice_id | Low |
| email_agent | send_email | to, subject, body | Medium |
| email_agent | read_inbox | limit | Low |
| admin_agent | delete_user | user_id | Critical |

### Map to Policy Rules

Convert your inventory to policy rules:

```json
{
  "rules": [
    {
      "action_type": "pay_invoice",
      "constraints": {
        "params.amount": {"max": 10000},
        "params.currency": {"in": ["USD", "EUR"]}
      },
      "allowed_agents": ["invoice_agent"]
    },
    {
      "action_type": "read_invoice"
    },
    {
      "action_type": "send_email",
      "constraints": {
        "params.to": {"pattern": ".*@(company\\.com|approved\\.com)$"}
      },
      "rate_limit": {"max_requests": 100, "window_seconds": 3600}
    },
    {
      "action_type": "read_inbox"
    },
    {
      "action_type": "delete_user",
      "allowed_agents": ["admin_agent"],
      "constraints": {
        "params.user_id": {"not_in": ["admin", "root", "system"]}
      }
    }
  ]
}
```

---

## Testing Your Migration

### Unit Tests

```python
import pytest
from ai_firewall import AIFirewall

@pytest.fixture
def firewall():
    return AIFirewall(
        api_key="test_key",
        project_id="test_project",
        base_url="http://localhost:8000"
    )

def test_valid_payment_allowed(firewall):
    result = firewall.execute(
        agent_name="invoice_agent",
        action_type="pay_invoice",
        params={"amount": 500, "currency": "USD"}
    )
    assert result.allowed is True

def test_excessive_payment_blocked(firewall):
    result = firewall.execute(
        agent_name="invoice_agent",
        action_type="pay_invoice",
        params={"amount": 50000, "currency": "USD"}
    )
    assert result.allowed is False
    assert "exceeds maximum" in result.reason

def test_unauthorized_agent_blocked(firewall):
    result = firewall.execute(
        agent_name="random_agent",
        action_type="delete_user",
        params={"user_id": "test123"}
    )
    assert result.allowed is False
```

### Integration Tests

```python
def test_full_workflow():
    # 1. Agent decides to perform action
    action = agent.decide_action()

    # 2. Validate with safety filter
    result = fw.execute(
        agent_name=agent.name,
        action_type=action.type,
        params=action.params
    )

    # 3. Verify expected behavior
    if action.type == "pay_invoice" and action.params["amount"] > 10000:
        assert result.allowed is False
    else:
        assert result.allowed is True
```

### Shadow Mode Testing

Run both old and new code paths:

```python
def execute_with_comparison(agent_name, action_type, params):
    # New path: validate
    result = fw.execute(agent_name, action_type, params)

    # Log discrepancies
    would_execute = not result.allowed
    did_execute = original_execute(action_type, params)

    if would_execute != did_execute:
        logger.warning(f"Discrepancy: filter={would_execute}, actual={did_execute}")

    return did_execute
```

---

## Rollback Plan

Always have a rollback strategy:

### Option 1: Feature Flag

```python
SAFETY_FILTER_ENABLED = os.getenv("SAFETY_FILTER_ENABLED", "false") == "true"

def execute_action(agent_name, action_type, params):
    if SAFETY_FILTER_ENABLED:
        result = fw.execute(agent_name, action_type, params)
        if not result.allowed:
            raise ActionBlockedError(result.reason)

    return original_execute(action_type, params)
```

### Option 2: Permissive Policy

Switch to a permissive policy instantly:

```bash
curl -X POST http://localhost:8000/policies/my-project \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"name": "emergency-permissive", "version": "999.0", "default": "allow", "rules": []}'
```

### Option 3: Bypass in Code

```python
BYPASS_SAFETY = os.getenv("BYPASS_SAFETY", "false") == "true"

def execute_action(agent_name, action_type, params):
    if not BYPASS_SAFETY:
        result = fw.execute(agent_name, action_type, params)
        if not result.allowed:
            raise ActionBlockedError(result.reason)

    return original_execute(action_type, params)
```

---

## Migration Checklist

- [ ] Set up AI Agent Safety Filter server
- [ ] Create project and save API key
- [ ] Inventory all agent actions
- [ ] Create initial permissive policy
- [ ] Add safety wrapper to code
- [ ] Deploy in shadow mode (log only)
- [ ] Collect 1-2 weeks of data
- [ ] Analyze blocked actions
- [ ] Refine policy rules
- [ ] Enable enforcement mode
- [ ] Monitor for issues
- [ ] Document rollback procedure

## Next Steps

- [Quickstart Guide](quickstart.md) - Basic setup
- [Policy Guide](policy-guide.md) - Detailed policy configuration
- [Best Practices](best-practices.md) - Policy design patterns
- [API Reference](api-reference.md) - Complete API documentation
