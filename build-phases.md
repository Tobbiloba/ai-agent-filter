# AI Agent Safety Filter - MVP Build Phases

## Overview

Total estimated build time: **3-4 hours**
Approach: Iterative, tested at each phase

---

## Phase 1: Project Foundation (20-30 min)

### Tasks
- [ ] Initialize project structure
- [ ] Set up FastAPI application skeleton
- [ ] Configure SQLite database with SQLAlchemy
- [ ] Create base configuration and environment handling
- [ ] Set up dependency management (requirements.txt / pyproject.toml)

### Deliverables
```
ai-firewall/
├── server/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   └── database.py
├── requirements.txt
└── .env.example
```

### Testing
- [ ] Server starts without errors
- [ ] Database connection works
- [ ] Health check endpoint returns 200

---

## Phase 2: Database Models (20-30 min)

### Tasks
- [ ] Define Project model (id, name, api_key, created_at)
- [ ] Define Policy model (id, project_id, rules, version, created_at)
- [ ] Define AuditLog model (id, project_id, agent_name, action_type, params, result, reason, timestamp)
- [ ] Create database migrations/initialization
- [ ] Add seed data helper

### Deliverables
```
server/
├── models/
│   ├── __init__.py
│   ├── project.py
│   ├── policy.py
│   └── audit_log.py
```

### Testing
- [ ] Models create tables correctly
- [ ] CRUD operations work for each model
- [ ] Relationships (project -> policies, project -> logs) work

---

## Phase 3: Policy Engine (30-45 min)

### Tasks
- [ ] Define policy schema/format (JSON-based rules)
- [ ] Implement rule types:
  - Parameter constraints (max/min values, allowed values)
  - Action type restrictions (whitelist/blacklist)
  - Rate limiting (actions per time window)
- [ ] Build policy loader and validator
- [ ] Implement rule evaluation engine
- [ ] Return structured allow/block responses with reasons

### Policy Schema Example
```json
{
  "version": "1.0",
  "rules": [
    {
      "action_type": "pay_invoice",
      "constraints": {
        "params.amount": {"max": 10000},
        "params.currency": {"in": ["USD", "EUR"]}
      }
    },
    {
      "action_type": "*",
      "rate_limit": {"max_requests": 100, "window_seconds": 3600}
    }
  ],
  "default": "allow"
}
```

### Deliverables
```
server/
├── services/
│   ├── __init__.py
│   ├── policy_engine.py
│   └── validator.py
```

### Testing
- [ ] Policy loads and parses correctly
- [ ] Parameter constraints block invalid values
- [ ] Parameter constraints allow valid values
- [ ] Action whitelist/blacklist works
- [ ] Rate limiting triggers after threshold
- [ ] Default allow/block behavior works
- [ ] Detailed rejection reasons returned

---

## Phase 4: API Endpoints (30-40 min)

### Tasks
- [ ] Implement API key authentication middleware
- [ ] POST `/validate_action` - main validation endpoint
- [ ] GET `/policies/{project_id}` - retrieve current policy
- [ ] POST `/policies/{project_id}` - create/update policy
- [ ] GET `/logs/{project_id}` - fetch audit logs (with pagination)
- [ ] POST `/projects` - create new project (returns API key)
- [ ] Add request/response validation with Pydantic

### Endpoint Specs

#### POST /validate_action
```json
// Request
{
  "project_id": "finbot-123",
  "agent_name": "invoice_agent",
  "action_type": "pay_invoice",
  "params": {"vendor": "VendorA", "amount": 5000}
}

// Response
{
  "allowed": true,
  "action_id": "act_abc123",
  "timestamp": "2025-12-07T10:30:00Z"
}

// Or blocked
{
  "allowed": false,
  "reason": "Amount 15000 exceeds maximum allowed 10000",
  "action_id": "act_abc123",
  "timestamp": "2025-12-07T10:30:00Z"
}
```

### Deliverables
```
server/
├── routes/
│   ├── __init__.py
│   ├── validate.py
│   ├── policies.py
│   ├── logs.py
│   └── projects.py
├── middleware/
│   ├── __init__.py
│   └── auth.py
├── schemas/
│   ├── __init__.py
│   ├── action.py
│   ├── policy.py
│   └── responses.py
```

### Testing
- [ ] Unauthenticated requests return 401
- [ ] Invalid API key returns 403
- [ ] `/validate_action` returns correct allow/block
- [ ] `/validate_action` creates audit log entry
- [ ] Policy CRUD operations work
- [ ] Logs endpoint returns paginated results
- [ ] Invalid request bodies return 422 with details

---

## Phase 5: Python SDK (25-35 min)

### Tasks
- [ ] Create SDK package structure
- [ ] Implement `AIFirewall` client class
- [ ] Add methods: `execute()`, `get_policy()`, `update_policy()`, `get_logs()`
- [ ] Handle errors gracefully (network, auth, validation)
- [ ] Add retry logic for transient failures
- [ ] Make it pip-installable

### SDK Interface
```python
from ai_firewall import AIFirewall

# Initialize
fw = AIFirewall(
    api_key="your-api-key",
    project_id="finbot-123",
    base_url="https://api.yourfirewall.com"  # optional
)

# Validate and execute
result = fw.execute(
    agent_name="invoice_agent",
    action_type="pay_invoice",
    params={"vendor": "VendorA", "amount": 5000}
)

if result.allowed:
    # proceed with action
    pass
else:
    print(f"Blocked: {result.reason}")

# Get logs
logs = fw.get_logs(limit=50)
```

### Deliverables
```
sdk/
└── python/
    ├── ai_firewall/
    │   ├── __init__.py
    │   ├── client.py
    │   ├── models.py
    │   └── exceptions.py
    ├── pyproject.toml
    └── README.md
```

### Testing
- [ ] SDK initializes correctly
- [ ] `execute()` sends correct request format
- [ ] `execute()` parses allow response correctly
- [ ] `execute()` parses block response correctly
- [ ] Network errors raise appropriate exceptions
- [ ] Auth errors raise `AuthenticationError`
- [ ] SDK works end-to-end with running server

---

## Phase 6: Integration Example (20-30 min)

### Tasks
- [ ] Create CrewAI integration example
- [ ] Create OpenAI Agents integration example (if time permits)
- [ ] Add inline documentation
- [ ] Show both allowed and blocked scenarios

### CrewAI Example
```python
from crewai import Agent, Task, Crew
from ai_firewall import AIFirewall

fw = AIFirewall(api_key="xxx", project_id="finbot-123")

def guarded_action(agent_name, action_type, params, action_fn):
    """Wrapper that validates before executing"""
    result = fw.execute(agent_name, action_type, params)
    if result.allowed:
        return action_fn(params)
    else:
        raise PermissionError(f"Action blocked: {result.reason}")

# Use in CrewAI task
def pay_invoice(params):
    # actual payment logic
    pass

# Guarded call
guarded_action(
    "invoice_agent",
    "pay_invoice",
    {"vendor": "VendorA", "amount": 5000},
    pay_invoice
)
```

### Deliverables
```
examples/
├── crewai_example.py
├── openai_agents_example.py
└── README.md
```

### Testing
- [ ] Examples run without errors
- [ ] Examples demonstrate allowed flow
- [ ] Examples demonstrate blocked flow

---

## Phase 7: Docker & Deployment Setup (20-25 min)

### Tasks
- [ ] Create Dockerfile for server
- [ ] Create docker-compose.yml (server + optional postgres)
- [ ] Add environment variable documentation
- [ ] Create deployment guide for common platforms (Railway, Fly.io)

### Deliverables
```
ai-firewall/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── deploy/
    └── README.md
```

### Testing
- [ ] `docker build` succeeds
- [ ] `docker-compose up` starts server
- [ ] Server accessible on configured port
- [ ] Environment variables load correctly

---

## Phase 8: Documentation & Polish (20-25 min)

### Tasks
- [ ] Write main README.md with:
  - Quick start guide
  - Installation instructions
  - Basic usage examples
  - API reference summary
  - Configuration options
- [ ] Add inline code comments where helpful
- [ ] Create CHANGELOG.md
- [ ] Add LICENSE file (MIT recommended)

### Deliverables
```
ai-firewall/
├── README.md
├── CHANGELOG.md
├── LICENSE
└── docs/
    ├── api-reference.md
    └── policy-guide.md
```

### Testing
- [ ] README instructions work from scratch
- [ ] All code examples in docs are correct

---

## Phase 9: Final Integration Testing (15-20 min)

### Tasks
- [ ] Run full end-to-end test scenario
- [ ] Test: Create project -> Set policy -> Validate actions -> Check logs
- [ ] Test SDK against running server
- [ ] Test Docker deployment
- [ ] Fix any remaining issues

### Test Scenarios
1. **Happy path**: Action within policy limits -> allowed
2. **Parameter violation**: Amount exceeds max -> blocked
3. **Unknown action**: Action not in whitelist -> blocked (if configured)
4. **Rate limiting**: Exceed request limit -> blocked
5. **Auth failure**: Bad API key -> 401/403
6. **Policy update**: Change policy -> new rules apply immediately

---

## Summary

| Phase | Focus | Time |
|-------|-------|------|
| 1 | Project Foundation | 20-30 min |
| 2 | Database Models | 20-30 min |
| 3 | Policy Engine | 30-45 min |
| 4 | API Endpoints | 30-40 min |
| 5 | Python SDK | 25-35 min |
| 6 | Integration Example | 20-30 min |
| 7 | Docker Setup | 20-25 min |
| 8 | Documentation | 20-25 min |
| 9 | Final Testing | 15-20 min |
| **Total** | | **3-4 hours** |

---

## What You'll Have at the End

A fully functional MVP with:
- Working API server (FastAPI)
- Policy-based action validation
- Audit logging
- Python SDK ready for pip install
- CrewAI integration example
- Docker deployment ready
- Documentation to onboard users

Ready to ship to early users and gather feedback.
