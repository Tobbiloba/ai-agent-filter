# LangChain Integration Guide

This guide covers how to integrate AI Firewall with LangChain to protect your AI agents from executing unauthorized or dangerous actions.

## Overview

AI Firewall provides three integration patterns for LangChain:

| Pattern | Best For | Complexity |
|---------|----------|------------|
| Tool Wrapper | New projects, selective protection | Low |
| Callback Handler | Existing agents, automatic protection | Medium |
| Protected Executor | Fastest integration, full protection | Low |

## Installation

```bash
pip install ai-firewall langchain langchain-openai
```

## Prerequisites

1. AI Firewall server running (`uvicorn server.app:app --reload`)
2. A project created with API key
3. A policy configured for your use case

---

## Pattern 1: Tool Wrapper

Wrap individual tools with the `@protected_tool` decorator. This gives you explicit control over which tools are protected.

### Basic Usage

```python
from ai_firewall import AIFirewall
from examples.langchain.tool_wrapper import protected_tool

fw = AIFirewall(
    api_key="af_your_key",
    project_id="my-project",
    base_url="http://localhost:8000"
)

@protected_tool(fw, "finance_agent")
def pay_invoice(vendor: str, amount: float) -> str:
    """Pay an invoice to a vendor."""
    # Your payment logic
    return f"Paid ${amount} to {vendor}"

# Actions are validated before execution
result = pay_invoice(vendor="Acme Corp", amount=5000)
# Returns: "Paid $5000 to Acme Corp"

result = pay_invoice(vendor="Acme Corp", amount=50000)
# Returns: "Action blocked by policy: Amount exceeds maximum"
```

### Custom Action Type

```python
@protected_tool(fw, "email_agent", action_type="send_notification")
def send_email(to: str, subject: str) -> str:
    """Send an email notification."""
    return f"Sent to {to}"
```

### Create Tool Programmatically

```python
from examples.langchain.tool_wrapper import create_protected_tool

def my_function(param: str) -> str:
    return f"Result: {param}"

tool = create_protected_tool(
    firewall=fw,
    agent_name="my_agent",
    func=my_function,
    name="my_tool",
    description="Does something useful"
)
```

---

## Pattern 2: Callback Handler

Use a callback handler to intercept all tool executions automatically. This is ideal for existing agents.

### Basic Usage

```python
from ai_firewall import AIFirewall
from examples.langchain.callback_handler import LangChainFirewallHandler

fw = AIFirewall(api_key="...", project_id="...")
handler = LangChainFirewallHandler(fw, agent_name="my_agent")

# Add to any LangChain component
result = agent.invoke(
    {"input": "Process payment for $500"},
    config={"callbacks": [handler]}
)
```

### Check Blocked Actions

```python
# After invocation
for action in handler.blocked_actions:
    print(f"Blocked: {action['tool']} - {action['reason']}")

# Get summary
summary = handler.get_summary()
print(f"Total: {summary['total_actions']}")
print(f"Allowed: {summary['allowed_count']}")
print(f"Blocked: {summary['blocked_count']}")
```

### Silent Mode (No Exceptions)

```python
handler = LangChainFirewallHandler(
    fw,
    agent_name="my_agent",
    raise_on_block=False  # Log but don't raise
)
```

---

## Pattern 3: Protected Agent Executor

Wrap the entire AgentExecutor for the simplest integration.

### Basic Usage

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
from ai_firewall import AIFirewall
from examples.langchain.protected_agent import ProtectedAgentExecutor

# Create your normal agent
agent_executor = AgentExecutor(agent=agent, tools=tools)

# Wrap with protection
fw = AIFirewall(api_key="...", project_id="...")
protected = ProtectedAgentExecutor(agent_executor, fw, "my_agent")

# Use normally
result = protected.invoke({"input": "Process payment"})
```

### One-Step Creation

```python
from examples.langchain.protected_agent import create_protected_agent

protected = create_protected_agent(
    agent=agent,
    tools=tools,
    firewall=fw,
    agent_name="finance_agent",
    verbose=True
)

result = protected.invoke({"input": "Pay invoice"})
```

### Async Support

```python
result = await protected.ainvoke({"input": "..."})
```

### Streaming

```python
for chunk in protected.stream({"input": "..."}):
    print(chunk)
```

---

## Complete Example

```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from ai_firewall import AIFirewall
from examples.langchain.protected_agent import ProtectedAgentExecutor

# Define tools
@tool
def pay_invoice(vendor: str, amount: float) -> str:
    """Pay an invoice to a vendor."""
    return f"Paid ${amount} to {vendor}"

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to a recipient."""
    return f"Email sent to {to}"

@tool
def execute_sql(query: str) -> str:
    """Execute a SQL query."""
    return f"Executed: {query}"

# Create agent
llm = ChatOpenAI(model="gpt-4")
tools = [pay_invoice, send_email, execute_sql]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant that can process payments and send emails."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Protect with AI Firewall
fw = AIFirewall(
    api_key="af_your_api_key",
    project_id="langchain-demo",
    base_url="http://localhost:8000"
)

protected = ProtectedAgentExecutor(executor, fw, agent_name="finance_agent")

# Run the agent
try:
    result = protected.invoke({
        "input": "Pay $500 to Acme Corp and send a confirmation email to finance@company.com"
    })
    print(result)
except PermissionError as e:
    print(f"Action blocked: {e}")

# Check summary
summary = protected.get_summary()
print(f"Actions: {summary['allowed_count']} allowed, {summary['blocked_count']} blocked")
```

---

## Policy Configuration

Create a policy that controls what the LangChain agent can do:

```bash
curl -X POST http://localhost:8000/policies/langchain-demo \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "name": "langchain-agent-policy",
    "version": "1.0",
    "default": "block",
    "rules": [
      {
        "action_type": "pay_invoice",
        "constraints": {
          "params.amount": {"max": 10000, "min": 0}
        }
      },
      {
        "action_type": "send_email",
        "constraints": {
          "params.to": {"pattern": ".*@company\\.com$"}
        }
      },
      {
        "action_type": "execute_sql",
        "blocked_agents": ["*"]
      }
    ]
  }'
```

This policy:
- Blocks all actions by default
- Allows payments up to $10,000
- Only allows emails to @company.com addresses
- Blocks all SQL execution

---

## Error Handling

### Catching Blocked Actions

```python
try:
    result = protected.invoke({"input": "..."})
except PermissionError as e:
    print(f"Blocked: {e}")
    # Provide helpful message to user
    # Log the incident
    # Take alternative action
```

### Custom Error Handling

```python
class CustomFirewallHandler(LangChainFirewallHandler):
    def on_tool_start(self, serialized, input_str, **kwargs):
        try:
            super().on_tool_start(serialized, input_str, **kwargs)
        except PermissionError as e:
            # Custom handling
            self.notify_security_team(serialized, input_str)
            raise
```

---

## Best Practices

1. **Start with `default: block`** - Only allow actions you explicitly permit

2. **Use meaningful agent names** - Makes audit logs easier to analyze
   ```python
   ProtectedAgentExecutor(executor, fw, "finance_agent_prod")
   ```

3. **Test policies before production** - Use the demo script
   ```bash
   python examples/langchain/demo.py --mock
   ```

4. **Monitor blocked actions** - Check audit logs regularly
   ```bash
   curl "http://localhost:8000/logs/your-project?allowed=false" \
     -H "X-API-Key: YOUR_KEY"
   ```

5. **Version your policies** - Track changes over time
   ```json
   {"name": "finance-policy", "version": "2.1"}
   ```

---

## Troubleshooting

### "Connection refused"

AI Firewall server not running:
```bash
uvicorn server.app:app --reload
```

### "Authentication failed"

Check your API key:
```python
fw = AIFirewall(
    api_key="af_your_actual_key",  # Must start with af_
    project_id="your-project"
)
```

### "Action blocked unexpectedly"

View your policy:
```bash
curl http://localhost:8000/policies/your-project \
  -H "X-API-Key: YOUR_KEY"
```

Check the audit log for the reason:
```bash
curl "http://localhost:8000/logs/your-project?allowed=false&limit=5" \
  -H "X-API-Key: YOUR_KEY"
```

---

## Next Steps

- [Policy Guide](../policy-guide.md) - Learn policy syntax
- [API Reference](../api-reference.md) - Full API documentation
- [Best Practices](../best-practices.md) - Production recommendations
