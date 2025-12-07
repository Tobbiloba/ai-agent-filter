# Customer Support Response Agent

An AI-powered customer support agent that demonstrates the AI Firewall protecting against:
- **PII Leakage**: Blocks responses containing SSN patterns
- **Unauthorized Ticket Closure**: Requires "reviewed" tag before closing
- **Agent Authorization**: Only allowed agents can perform actions

## Architecture

```
Customer Ticket → AI Agent (Ollama) → AI Firewall → Ticket System
                      ↓                    ↓
                 Decides action      Validates/Blocks
```

## Firewall Rules

```yaml
send_response:
  - Block if response contains SSN pattern (XXX-XX-XXXX)
  - Rate limit: 50 requests/minute

close_ticket:
  - REQUIRE has_reviewed_tag = true
  - Only support_agent can close tickets

default: BLOCK all other actions
```

## Test Results

| Test | Scenario | Expected | Result |
|------|----------|----------|--------|
| 1 | Normal response (no PII) | ALLOWED | PASS |
| 2 | Response with SSN "123-45-6789" | BLOCKED | PASS |
| 3 | Close ticket without review tag | BLOCKED | PASS |
| 4 | Close ticket with review tag | ALLOWED | PASS |
| 5 | Response with email (allowed) | ALLOWED | PASS |
| 6 | Unauthorized agent | BLOCKED | PASS |

## Quick Start

```bash
# 1. Start the firewall server (from project root)
cd ../..
source venv/bin/activate
uvicorn server.app:app --port 8000

# 2. Setup the project and policy
cd sample-projects/support-agent
python3 firewall_setup.py

# 3. Run tests (validates firewall rules)
python3 test_scenarios.py

# 4. Run AI demo with Ollama
export FIREWALL_API_KEY='your-key'
export FIREWALL_PROJECT_ID='your-project-id'
python3 demo.py
```

## Files

- `ticket_system.py` - Simulated ticket management system
- `agent.py` - AI support agent using Ollama
- `firewall_setup.py` - Creates project and policy
- `test_scenarios.py` - Direct firewall rule tests
- `demo.py` - Full AI + firewall demo

## Key Scenarios

### 1. PII Protection
The AI might accidentally echo back sensitive data from customer messages:
```
Customer: "Update my SSN to 123-45-6789"
AI Response: "I've updated your SSN to 123-45-6789"  # BLOCKED!
```

### 2. Review Requirement
Prevents premature ticket closure:
```
Agent: close_ticket(TKT-001, has_reviewed_tag=False)  # BLOCKED
Agent: close_ticket(TKT-001, has_reviewed_tag=True)   # ALLOWED
```

### 3. Agent Authorization
Only authorized agents can perform actions:
```
support_agent: close_ticket(...)  # ALLOWED
random_agent: close_ticket(...)   # BLOCKED
```
