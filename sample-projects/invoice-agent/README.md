# Invoice Payment Agent - Sample Project

This is a sample AI agent that processes invoice payments, protected by the AI Firewall.

## What It Does

The agent receives invoice data and decides whether to pay them. Before any payment is executed, the action is validated through the AI Firewall to ensure:

1. Amount is within allowed limits ($500 max)
2. Vendor is on the approved list
3. Invoice hasn't been paid already (duplicate prevention)
4. Rate limits aren't exceeded

## Architecture

```
User Request → AI Agent (GPT-4) → Firewall Validation → Payment Execution
                    ↓                      ↓
              Suggests action         Allow/Block
              (pay_invoice)           decision
```

## Firewall Policy

```json
{
  "name": "invoice-agent-policy",
  "version": "1.0",
  "default": "block",
  "rules": [
    {
      "action_type": "pay_invoice",
      "constraints": {
        "params.amount": {"max": 500, "min": 1},
        "params.vendor": {"in": ["VendorA", "VendorB", "VendorC"]}
      },
      "allowed_agents": ["invoice_agent"],
      "rate_limit": {"max_requests": 10, "window_seconds": 60}
    }
  ]
}
```

## Test Scenarios

| Scenario | Invoice | Expected | Reason |
|----------|---------|----------|--------|
| Valid payment | $450 to VendorA | ✅ Allowed | Within limits |
| Amount too high | $600 to VendorA | ❌ Blocked | Exceeds $500 max |
| Unknown vendor | $100 to UnknownCorp | ❌ Blocked | Not in approved list |
| Duplicate invoice | Same invoice twice | ❌ Blocked | Already paid |
| Rate limit | 11 payments in 1 min | ❌ Blocked | Rate limit exceeded |

## Setup

1. **Start the AI Firewall server** (from the main project):
   ```bash
   cd /path/to/ai-agent-filter
   source venv/bin/activate
   uvicorn server.app:app --port 8000
   ```

2. **Set up this project**:
   ```bash
   cd sample-projects/invoice-agent
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key
   ```

4. **Run the demo**:
   ```bash
   python run_demo.py
   ```

## Files

- `agent.py` - The AI Invoice Agent using OpenAI
- `firewall_setup.py` - Sets up the firewall project and policy
- `payment_system.py` - Simulated payment backend
- `run_demo.py` - Interactive demo script
- `test_scenarios.py` - Automated test scenarios

## Running Without OpenAI

If you don't have an OpenAI API key, use `run_demo_mock.py` which simulates the AI responses.
