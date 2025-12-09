# LangChain Agent - Sample Project

A sample AI agent built with LangChain, protected by the AI Firewall. This project demonstrates all three integration patterns.

## What It Does

The agent is a finance assistant that can:
- **Pay invoices** - Validated: max $10,000, USD/EUR/GBP only
- **Send emails** - Validated: only to @company.com or @example.com
- **Search database** - Allowed without restrictions
- **Execute SQL** - Blocked for all agents (dangerous!)

## Architecture

```
User Request → LangChain Agent (GPT-4) → AI Firewall → Tool Execution
                      ↓                       ↓
                 Decides action          Allow/Block
                                         decision
```

## Quick Start

### 1. Run Integration Tests (No LLM needed)

```bash
# Test with mock firewall (no server required)
python test_integration.py --mock

# Test with real firewall (server must be running)
python test_integration.py
```

### 2. Full Setup

```bash
# 1. Start AI Firewall server (from project root)
cd ../..
source venv/bin/activate
uvicorn server.app:app --reload

# 2. Set up project and policy
cd sample-projects/langchain-agent
python firewall_setup.py

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Run tests
python test_integration.py
```

## Integration Patterns Demonstrated

### Pattern 1: Tool Wrapper

Each tool is individually wrapped with firewall protection:

```python
from examples.langchain.tool_wrapper import protected_tool

fw = AIFirewall(api_key="...", project_id="...")

@protected_tool(fw, "finance_agent")
def pay_invoice(vendor: str, amount: float) -> str:
    """Pay an invoice to a vendor."""
    return process_payment(vendor, amount)
```

### Pattern 2: Callback Handler

All tool calls are intercepted via LangChain's callback system:

```python
from examples.langchain.callback_handler import LangChainFirewallHandler

handler = LangChainFirewallHandler(fw, agent_name="finance_agent")

result = agent.invoke(
    {"input": "Pay invoice #123"},
    config={"callbacks": [handler]}
)

# Check what was blocked
print(handler.blocked_actions)
```

### Pattern 3: Protected Executor

Wrap the entire AgentExecutor:

```python
from examples.langchain.protected_agent import ProtectedAgentExecutor

protected = ProtectedAgentExecutor(agent_executor, fw, "finance_agent")

result = protected.invoke({"input": "Pay invoice #123"})
print(protected.get_summary())
```

## Firewall Policy

```json
{
  "name": "langchain-agent-policy",
  "version": "1.0",
  "default": "block",
  "rules": [
    {
      "action_type": "pay_invoice",
      "constraints": {
        "params.amount": {"max": 10000, "min": 1},
        "params.currency": {"in": ["USD", "EUR", "GBP"]}
      },
      "rate_limit": {"max_requests": 5, "window_seconds": 60}
    },
    {
      "action_type": "send_email",
      "constraints": {
        "params.to": {"pattern": ".*@(company\\.com|example\\.com)$"}
      }
    },
    {
      "action_type": "search_database"
    },
    {
      "action_type": "execute_sql",
      "blocked_agents": ["*"]
    }
  ]
}
```

## Test Scenarios

| Action | Parameters | Expected | Reason |
|--------|------------|----------|--------|
| pay_invoice | $5,000 USD | ✅ Allowed | Within limits |
| pay_invoice | $50,000 USD | ❌ Blocked | Exceeds $10,000 max |
| pay_invoice | $5,000 JPY | ❌ Blocked | Currency not allowed |
| send_email | user@company.com | ✅ Allowed | Domain allowed |
| send_email | user@evil.com | ❌ Blocked | Domain not allowed |
| search_database | any | ✅ Allowed | No restrictions |
| execute_sql | any | ❌ Blocked | Blocked for all agents |

## Files

| File | Description |
|------|-------------|
| `tools.py` | Tool definitions (pay_invoice, send_email, etc.) |
| `agent.py` | LangChain agent setup with firewall integration |
| `firewall_setup.py` | Sets up project and policy on firewall server |
| `test_integration.py` | Integration tests for all patterns |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variables template |

## Running Without OpenAI

The integration tests can run without an OpenAI API key using `--mock` mode:

```bash
python test_integration.py --mock
```

This tests the firewall integration logic without making LLM calls.

## Troubleshooting

### "FIREWALL_API_KEY not set"

Run `python firewall_setup.py` first to create a project and get an API key.

### "Cannot connect to firewall"

Make sure the server is running:
```bash
cd ../..
uvicorn server.app:app --reload
```

### "langchain not found"

Install dependencies:
```bash
pip install -r requirements.txt
```
