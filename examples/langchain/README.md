# LangChain Integration

Protect your LangChain agents with AI Firewall. This directory contains three integration patterns and a runnable demo.

## Quick Start

```bash
# Install dependencies
pip install langchain langchain-openai ai-firewall

# Run demo (mock mode, no server needed)
python demo.py --mock

# Run demo (with AI Firewall server)
python demo.py
```

## Integration Patterns

### Pattern 1: Tool Wrapper (Recommended for new projects)

Wrap individual tools with the `@protected_tool` decorator:

```python
from ai_firewall import AIFirewall
from tool_wrapper import protected_tool

fw = AIFirewall(api_key="...", project_id="...")

@protected_tool(fw, "invoice_agent")
def pay_invoice(vendor: str, amount: float) -> str:
    """Pay an invoice to a vendor."""
    return f"Paid ${amount} to {vendor}"

# Tool is now protected - actions are validated before execution
result = pay_invoice(vendor="Acme", amount=5000)
```

**When to use:** New projects, when you want explicit control over which tools are protected.

### Pattern 2: Callback Handler (Recommended for existing agents)

Intercept all tool calls with a callback handler:

```python
from ai_firewall import AIFirewall
from callback_handler import LangChainFirewallHandler

fw = AIFirewall(api_key="...", project_id="...")
handler = LangChainFirewallHandler(fw, agent_name="my_agent")

# Add handler to any LangChain component
result = agent.invoke(
    {"input": "Pay invoice #123"},
    config={"callbacks": [handler]}
)

# Check what was blocked
print(handler.blocked_actions)
```

**When to use:** Existing agents, when you want to protect all tools without modifying them.

### Pattern 3: Protected Agent Executor (Easiest)

Wrap the entire AgentExecutor:

```python
from ai_firewall import AIFirewall
from protected_agent import ProtectedAgentExecutor

fw = AIFirewall(api_key="...", project_id="...")

# Create your normal agent
agent_executor = AgentExecutor(agent=agent, tools=tools)

# Wrap with protection
protected = ProtectedAgentExecutor(agent_executor, fw, "my_agent")

# Use normally - all tools are now protected
result = protected.invoke({"input": "Process payment"})

# Check results
print(protected.get_summary())
```

**When to use:** Fastest integration, one-line protection for an entire agent.

## Files

| File | Description |
|------|-------------|
| `tool_wrapper.py` | `@protected_tool` decorator and `create_protected_tool` function |
| `callback_handler.py` | `FirewallCallbackHandler` and `LangChainFirewallHandler` |
| `protected_agent.py` | `ProtectedAgentExecutor` and `create_protected_agent` |
| `demo.py` | Runnable demo showing all patterns |
| `requirements.txt` | Dependencies |

## Full Example

```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from ai_firewall import AIFirewall
from protected_agent import ProtectedAgentExecutor

# 1. Create your tools
@tool
def pay_invoice(vendor: str, amount: float) -> str:
    """Pay an invoice to a vendor."""
    # Your payment logic here
    return f"Paid ${amount} to {vendor}"

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    # Your email logic here
    return f"Email sent to {to}"

# 2. Create your agent
llm = ChatOpenAI(model="gpt-4")
tools = [pay_invoice, send_email]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 3. Wrap with AI Firewall
fw = AIFirewall(
    api_key="af_your_key_here",
    project_id="your-project",
    base_url="http://localhost:8000"
)

protected = ProtectedAgentExecutor(executor, fw, agent_name="finance_agent")

# 4. Use normally
try:
    result = protected.invoke({"input": "Pay $500 to Acme Corp"})
    print(result)
except PermissionError as e:
    print(f"Action blocked: {e}")

# 5. Check what happened
summary = protected.get_summary()
print(f"Allowed: {summary['allowed_count']}, Blocked: {summary['blocked_count']}")
```

## Policy Example

Set up a policy on the AI Firewall server:

```bash
curl -X POST http://localhost:8000/policies/your-project \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "name": "langchain-policy",
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
      }
    ]
  }'
```

This policy:
- Blocks all actions by default
- Allows `pay_invoice` up to $10,000
- Allows `send_email` only to @company.com addresses

## Error Handling

### With raise_on_block=True (default)

```python
try:
    result = protected.invoke({"input": "..."})
except PermissionError as e:
    # Handle blocked action
    print(f"Action blocked: {e}")
```

### With raise_on_block=False

```python
handler = FirewallCallbackHandler(fw, raise_on_block=False)
result = agent.invoke({"input": "..."}, config={"callbacks": [handler]})

# Check blocked actions after
for blocked in handler.blocked_actions:
    print(f"Blocked: {blocked['tool']} - {blocked['reason']}")
```

## Best Practices

1. **Start restrictive**: Use `default: "block"` in policies
2. **Log everything**: All actions are logged in the audit trail
3. **Test policies**: Run `demo.py` to verify behavior before production
4. **Use meaningful agent names**: Makes audit logs easier to analyze
5. **Handle PermissionError**: Provide helpful feedback when actions are blocked

## Troubleshooting

### "Could not connect to AI Firewall"

Make sure the server is running:
```bash
cd /path/to/ai-firewall
uvicorn server.app:app --reload
```

### "Action blocked unexpectedly"

Check your policy:
```bash
curl http://localhost:8000/policies/your-project \
  -H "X-API-Key: YOUR_KEY"
```

### "Module not found"

Install dependencies:
```bash
pip install -r requirements.txt
```

## More Information

- [AI Firewall Documentation](../../docs/)
- [Policy Guide](../../docs/policy-guide.md)
- [API Reference](../../docs/api-reference.md)
