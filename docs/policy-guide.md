# Policy Guide

This guide explains how to write effective policies for the AI Agent Safety Filter.

## Policy Structure

A policy is a JSON document with the following structure:

```json
{
  "name": "policy-name",
  "version": "1.0",
  "default": "allow",
  "rules": [
    // Array of rules
  ]
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Human-readable name (default: "default") |
| `version` | string | No | Version identifier (default: "1.0") |
| `default` | string | No | "allow" or "block" - behavior when no rules match |
| `rules` | array | Yes | List of rule objects |

## Rules

Each rule defines conditions for allowing or blocking actions.

```json
{
  "action_type": "pay_invoice",
  "constraints": {...},
  "allowed_agents": [...],
  "blocked_agents": [...],
  "rate_limit": {...}
}
```

### action_type

The type of action this rule applies to. Use `"*"` to match all actions.

```json
{"action_type": "pay_invoice"}  // Specific action
{"action_type": "*"}             // All actions
```

### constraints

Parameter constraints validate the action's parameters.

#### max / min

Numeric bounds:

```json
{
  "constraints": {
    "params.amount": {"max": 10000, "min": 0}
  }
}
```

#### in (whitelist)

Only allow specific values:

```json
{
  "constraints": {
    "params.currency": {"in": ["USD", "EUR", "GBP"]}
  }
}
```

#### not_in (blacklist)

Block specific values:

```json
{
  "constraints": {
    "params.vendor": {"not_in": ["BlockedVendor", "UntrustedCorp"]}
  }
}
```

#### pattern (regex)

Match against a regular expression:

```json
{
  "constraints": {
    "params.email": {"pattern": ".*@company\\.com$"}
  }
}
```

#### equals

Exact match:

```json
{
  "constraints": {
    "params.environment": {"equals": "production"}
  }
}
```

### Nested Parameters

Use dot notation to access nested parameters:

```json
{
  "constraints": {
    "params.payment.amount": {"max": 10000},
    "params.payment.recipient.country": {"in": ["US", "CA"]}
  }
}
```

For the action:
```json
{
  "params": {
    "payment": {
      "amount": 5000,
      "recipient": {
        "country": "US"
      }
    }
  }
}
```

### allowed_agents

Whitelist of agents that can perform this action:

```json
{
  "action_type": "delete_database",
  "allowed_agents": ["admin_agent", "maintenance_agent"]
}
```

Other agents will be blocked.

### blocked_agents

Blacklist of agents that cannot perform this action:

```json
{
  "action_type": "send_email",
  "blocked_agents": ["untrusted_agent", "test_agent"]
}
```

### rate_limit

Limit the number of actions in a time window:

```json
{
  "action_type": "api_call",
  "rate_limit": {
    "max_requests": 100,
    "window_seconds": 3600
  }
}
```

This allows 100 requests per hour per agent per action type.

## Rule Evaluation

1. Rules are evaluated in order
2. Specific `action_type` rules are checked before wildcard (`*`) rules
3. If a rule blocks the action, evaluation stops
4. If no rules match, the `default` behavior applies

## Examples

### Finance Bot Policy

```json
{
  "name": "finance-bot-production",
  "version": "1.0",
  "default": "block",
  "rules": [
    {
      "action_type": "pay_invoice",
      "constraints": {
        "params.amount": {"max": 10000, "min": 0},
        "params.currency": {"in": ["USD", "EUR"]}
      },
      "allowed_agents": ["invoice_agent", "payment_agent"]
    },
    {
      "action_type": "transfer_funds",
      "constraints": {
        "params.amount": {"max": 5000},
        "params.destination_type": {"in": ["internal"]}
      }
    },
    {
      "action_type": "read_balance",
      "allowed_agents": ["*"]
    }
  ]
}
```

This policy:
- Blocks all actions by default
- Allows invoice payments up to $10,000 in USD/EUR
- Only allows internal transfers up to $5,000
- Allows any agent to read balances

### Customer Service Bot Policy

```json
{
  "name": "support-bot",
  "version": "1.0",
  "default": "allow",
  "rules": [
    {
      "action_type": "send_email",
      "constraints": {
        "params.to": {"pattern": ".*@(company\\.com|customer\\.com)$"}
      }
    },
    {
      "action_type": "refund",
      "constraints": {
        "params.amount": {"max": 100}
      }
    },
    {
      "action_type": "delete_account",
      "blocked_agents": ["*"]
    },
    {
      "action_type": "*",
      "rate_limit": {
        "max_requests": 1000,
        "window_seconds": 3600
      }
    }
  ]
}
```

This policy:
- Allows most actions by default
- Restricts emails to company/customer domains
- Limits refunds to $100
- Blocks all account deletions
- Rate limits all actions to 1000/hour

### Research Agent Policy

```json
{
  "name": "research-agent",
  "version": "1.0",
  "default": "allow",
  "rules": [
    {
      "action_type": "web_search",
      "rate_limit": {
        "max_requests": 50,
        "window_seconds": 60
      }
    },
    {
      "action_type": "download_file",
      "constraints": {
        "params.size_mb": {"max": 100},
        "params.file_type": {"in": ["pdf", "csv", "json", "txt"]}
      }
    },
    {
      "action_type": "execute_code",
      "blocked_agents": ["*"]
    },
    {
      "action_type": "access_database",
      "constraints": {
        "params.operation": {"in": ["read"]}
      }
    }
  ]
}
```

This policy:
- Allows web searches with rate limiting
- Restricts file downloads by size and type
- Blocks all code execution
- Only allows read-only database access

## Best Practices

### 1. Start Restrictive

Use `default: "block"` and explicitly allow actions:

```json
{
  "default": "block",
  "rules": [
    {"action_type": "safe_action_1"},
    {"action_type": "safe_action_2"}
  ]
}
```

### 2. Version Your Policies

Increment version when making changes for audit trail:

```json
{"version": "1.0"}  // Initial
{"version": "1.1"}  // Minor change
{"version": "2.0"}  // Major change
```

### 3. Use Specific Rules First

Order rules from specific to general:

```json
{
  "rules": [
    {"action_type": "pay_invoice", "constraints": {...}},
    {"action_type": "pay_*", "constraints": {...}},
    {"action_type": "*", "rate_limit": {...}}
  ]
}
```

### 4. Combine Constraints

Use multiple constraints for defense in depth:

```json
{
  "action_type": "transfer_funds",
  "constraints": {
    "params.amount": {"max": 10000},
    "params.currency": {"in": ["USD"]},
    "params.destination": {"pattern": "^[A-Z0-9]{10}$"}
  },
  "allowed_agents": ["transfer_agent"],
  "rate_limit": {"max_requests": 10, "window_seconds": 3600}
}
```

### 5. Test Both Paths

Always test that:
- Valid actions are allowed
- Invalid actions are blocked
- Edge cases are handled

```python
# Test allowed
result = fw.execute("agent", "action", {"amount": 5000})
assert result.allowed == True

# Test blocked
result = fw.execute("agent", "action", {"amount": 50000})
assert result.allowed == False
```

## Debugging Policies

### Check Current Policy

```bash
curl http://localhost:8000/policies/my-project \
  -H "X-API-Key: af_xxx"
```

### View Blocked Actions

```bash
curl "http://localhost:8000/logs/my-project?allowed=false" \
  -H "X-API-Key: af_xxx"
```

The `reason` field explains why each action was blocked.

### Common Issues

**Action blocked unexpectedly:**
- Check if `default` is "block"
- Verify agent name matches `allowed_agents`
- Check parameter values against constraints

**Action allowed when it shouldn't be:**
- Ensure rule `action_type` matches exactly
- Check constraint field names (use `params.` prefix)
- Verify constraint values are correct types
