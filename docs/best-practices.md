# Best Practices Guide

Design patterns and recommendations for effective AI agent safety policies.

## Core Principles

### 1. Default Deny

Start with `"default": "block"` and explicitly allow actions:

```json
{
  "default": "block",
  "rules": [
    {"action_type": "read_data"},
    {"action_type": "send_notification"},
    {"action_type": "generate_report"}
  ]
}
```

**Why:** Unknown or new actions are blocked until reviewed. This prevents agents from performing unexpected actions.

### 2. Least Privilege

Grant only the minimum permissions needed:

```json
{
  "action_type": "transfer_funds",
  "constraints": {
    "params.amount": {"max": 1000},
    "params.destination_type": {"in": ["internal"]}
  },
  "allowed_agents": ["treasury_agent"]
}
```

**Why:** Limits blast radius if an agent is compromised or misbehaves.

### 3. Defense in Depth

Combine multiple safety mechanisms:

```json
{
  "action_type": "delete_record",
  "constraints": {
    "params.record_type": {"in": ["temporary", "draft"]},
    "params.age_days": {"min": 30}
  },
  "allowed_agents": ["cleanup_agent"],
  "rate_limit": {"max_requests": 100, "window_seconds": 3600}
}
```

**Why:** Multiple layers ensure safety even if one mechanism fails.

---

## Policy Design Patterns

### Pattern 1: Tiered Access

Different limits for different risk levels:

```json
{
  "rules": [
    {
      "action_type": "approve_expense",
      "constraints": {"params.amount": {"max": 100}},
      "allowed_agents": ["junior_agent"]
    },
    {
      "action_type": "approve_expense",
      "constraints": {"params.amount": {"max": 10000}},
      "allowed_agents": ["senior_agent"]
    },
    {
      "action_type": "approve_expense",
      "allowed_agents": ["executive_agent"]
    }
  ]
}
```

**Use case:** When different agents need different permission levels.

### Pattern 2: Environment Isolation

Separate policies per environment:

```json
// production-policy.json
{
  "name": "production",
  "default": "block",
  "rules": [
    {
      "action_type": "send_email",
      "constraints": {
        "params.to": {"pattern": ".*@(company\\.com|partner\\.com)$"}
      }
    }
  ]
}

// staging-policy.json
{
  "name": "staging",
  "default": "allow",
  "rules": [
    {
      "action_type": "send_email",
      "constraints": {
        "params.to": {"pattern": ".*@test\\.company\\.com$"}
      }
    }
  ]
}
```

**Use case:** Tighter controls in production, more freedom in dev/staging.

### Pattern 3: Action Categories

Group related actions with consistent rules:

```json
{
  "rules": [
    // Read operations - broadly allowed
    {"action_type": "read_customer", "rate_limit": {"max_requests": 1000, "window_seconds": 60}},
    {"action_type": "read_order", "rate_limit": {"max_requests": 1000, "window_seconds": 60}},
    {"action_type": "read_inventory", "rate_limit": {"max_requests": 1000, "window_seconds": 60}},

    // Write operations - restricted
    {"action_type": "update_customer", "allowed_agents": ["customer_agent"], "rate_limit": {"max_requests": 100, "window_seconds": 60}},
    {"action_type": "create_order", "allowed_agents": ["order_agent"], "rate_limit": {"max_requests": 100, "window_seconds": 60}},

    // Delete operations - highly restricted
    {"action_type": "delete_customer", "allowed_agents": ["admin_agent"], "rate_limit": {"max_requests": 10, "window_seconds": 3600}},
    {"action_type": "delete_order", "allowed_agents": ["admin_agent"], "rate_limit": {"max_requests": 10, "window_seconds": 3600}}
  ]
}
```

**Use case:** CRUD operations with increasing restrictions.

### Pattern 4: Time-Based Limits

Use rate limiting for temporal controls:

```json
{
  "rules": [
    {
      "action_type": "bulk_email",
      "rate_limit": {"max_requests": 1, "window_seconds": 86400}
    },
    {
      "action_type": "generate_report",
      "rate_limit": {"max_requests": 10, "window_seconds": 3600}
    },
    {
      "action_type": "api_call",
      "rate_limit": {"max_requests": 60, "window_seconds": 60}
    }
  ]
}
```

**Use case:** Prevent resource exhaustion and abuse.

### Pattern 5: Domain-Specific Validation

Use regex patterns for domain validation:

```json
{
  "rules": [
    {
      "action_type": "send_email",
      "constraints": {
        "params.to": {"pattern": "^[a-zA-Z0-9._%+-]+@(company|partner)\\.com$"}
      }
    },
    {
      "action_type": "access_url",
      "constraints": {
        "params.url": {"pattern": "^https://(api|docs)\\.company\\.com/.*$"}
      }
    },
    {
      "action_type": "execute_query",
      "constraints": {
        "params.query": {"pattern": "^SELECT\\s+.*$"}
      }
    }
  ]
}
```

**Use case:** Validate data formats and restrict to approved domains.

### Pattern 6: Negative Rules (Blacklist Specific Values)

Block known-bad values:

```json
{
  "rules": [
    {
      "action_type": "access_file",
      "constraints": {
        "params.path": {"not_in": ["/etc/passwd", "/etc/shadow", "~/.ssh/id_rsa"]}
      }
    },
    {
      "action_type": "run_command",
      "constraints": {
        "params.command": {"not_in": ["rm -rf", "sudo", "chmod 777"]}
      }
    },
    {
      "action_type": "modify_user",
      "constraints": {
        "params.user_id": {"not_in": ["admin", "root", "system"]}
      }
    }
  ]
}
```

**Use case:** Block specific dangerous operations.

---

## Common Use Cases

### Financial Agent

```json
{
  "name": "finance-policy",
  "version": "1.0",
  "default": "block",
  "rules": [
    {
      "action_type": "pay_invoice",
      "constraints": {
        "params.amount": {"max": 10000, "min": 0},
        "params.currency": {"in": ["USD", "EUR", "GBP"]}
      },
      "allowed_agents": ["payment_agent", "invoice_agent"],
      "rate_limit": {"max_requests": 50, "window_seconds": 3600}
    },
    {
      "action_type": "transfer_funds",
      "constraints": {
        "params.amount": {"max": 5000},
        "params.destination_type": {"equals": "internal"}
      },
      "allowed_agents": ["treasury_agent"]
    },
    {
      "action_type": "read_balance"
    },
    {
      "action_type": "read_transactions",
      "rate_limit": {"max_requests": 100, "window_seconds": 60}
    }
  ]
}
```

### Customer Service Agent

```json
{
  "name": "support-policy",
  "version": "1.0",
  "default": "allow",
  "rules": [
    {
      "action_type": "issue_refund",
      "constraints": {
        "params.amount": {"max": 100}
      }
    },
    {
      "action_type": "send_email",
      "constraints": {
        "params.to": {"pattern": ".*@customer\\.com$"}
      },
      "rate_limit": {"max_requests": 200, "window_seconds": 3600}
    },
    {
      "action_type": "access_account",
      "constraints": {
        "params.fields": {"in": ["name", "email", "order_history"]}
      }
    },
    {
      "action_type": "delete_account",
      "blocked_agents": ["*"]
    },
    {
      "action_type": "modify_billing",
      "blocked_agents": ["*"]
    }
  ]
}
```

### Research Agent

```json
{
  "name": "research-policy",
  "version": "1.0",
  "default": "block",
  "rules": [
    {
      "action_type": "web_search",
      "rate_limit": {"max_requests": 100, "window_seconds": 60}
    },
    {
      "action_type": "fetch_url",
      "constraints": {
        "params.url": {"pattern": "^https://.*$"}
      },
      "rate_limit": {"max_requests": 50, "window_seconds": 60}
    },
    {
      "action_type": "read_document"
    },
    {
      "action_type": "save_note"
    },
    {
      "action_type": "execute_code",
      "blocked_agents": ["*"]
    },
    {
      "action_type": "access_database",
      "constraints": {
        "params.operation": {"equals": "read"}
      }
    }
  ]
}
```

### DevOps Agent

```json
{
  "name": "devops-policy",
  "version": "1.0",
  "default": "block",
  "rules": [
    {
      "action_type": "deploy",
      "constraints": {
        "params.environment": {"in": ["staging", "dev"]}
      },
      "allowed_agents": ["deploy_agent"]
    },
    {
      "action_type": "deploy",
      "constraints": {
        "params.environment": {"equals": "production"}
      },
      "allowed_agents": ["senior_deploy_agent"],
      "rate_limit": {"max_requests": 5, "window_seconds": 3600}
    },
    {
      "action_type": "restart_service",
      "constraints": {
        "params.service": {"not_in": ["database", "auth", "payment"]}
      },
      "rate_limit": {"max_requests": 10, "window_seconds": 3600}
    },
    {
      "action_type": "view_logs"
    },
    {
      "action_type": "view_metrics"
    },
    {
      "action_type": "delete_data",
      "blocked_agents": ["*"]
    }
  ]
}
```

---

## Anti-Patterns to Avoid

### 1. Overly Permissive Default

**Bad:**
```json
{
  "default": "allow",
  "rules": []
}
```

**Why:** Any action passes. New or unexpected actions won't be caught.

### 2. Missing Rate Limits

**Bad:**
```json
{
  "action_type": "send_email"
}
```

**Better:**
```json
{
  "action_type": "send_email",
  "rate_limit": {"max_requests": 100, "window_seconds": 3600}
}
```

**Why:** Without rate limits, a misbehaving agent can spam actions.

### 3. Trusting Input Format

**Bad:**
```json
{
  "action_type": "execute_query",
  "constraints": {
    "params.query": {"pattern": "^SELECT.*"}
  }
}
```

**Better:**
```json
{
  "action_type": "execute_query",
  "constraints": {
    "params.query": {"pattern": "^SELECT\\s+[a-zA-Z0-9_,\\s]+\\s+FROM\\s+[a-zA-Z0-9_]+\\s*(WHERE.*)?$"}
  }
}
```

**Why:** Weak patterns can be bypassed (e.g., `SELECT * FROM users; DROP TABLE users;--`).

### 4. No Agent Restrictions

**Bad:**
```json
{
  "action_type": "delete_user"
}
```

**Better:**
```json
{
  "action_type": "delete_user",
  "allowed_agents": ["admin_agent"]
}
```

**Why:** Any agent can perform critical actions.

### 5. Static Limits

**Bad:**
```json
{
  "constraints": {
    "params.amount": {"max": 999999}
  }
}
```

**Better:**
```json
{
  "constraints": {
    "params.amount": {"max": 10000}
  },
  "rate_limit": {"max_requests": 10, "window_seconds": 3600}
}
```

**Why:** Even if individual amounts are reasonable, rapid repeated actions can cause damage.

---

## Monitoring and Iteration

### Regular Audits

1. **Weekly:** Review blocked actions
   ```bash
   curl "http://localhost:8000/logs/my-project?allowed=false&page_size=100" \
     -H "X-API-Key: YOUR_KEY"
   ```

2. **Monthly:** Review statistics
   ```bash
   curl "http://localhost:8000/logs/my-project/stats" \
     -H "X-API-Key: YOUR_KEY"
   ```

3. **Quarterly:** Full policy review

### Metrics to Watch

- **Block rate:** Should be low (<5%) if policy is well-tuned
- **Top blocked actions:** May indicate missing rules or policy issues
- **Top agents:** Ensure distribution matches expected usage
- **Rate limit hits:** May need to adjust limits

### Version Control

Keep policies in version control:

```
policies/
├── production/
│   └── finance-policy.json
├── staging/
│   └── finance-policy.json
└── CHANGELOG.md
```

Document changes in CHANGELOG:
```markdown
## [2.0] - 2025-12-09
- Increased payment limit from $5000 to $10000
- Added treasury_agent to transfer_funds allowlist

## [1.1] - 2025-11-15
- Added rate limiting to all read operations
- Blocked delete_all action for all agents
```

---

## Summary Checklist

- [ ] Default is "block" (deny-by-default)
- [ ] Each action type has explicit rules
- [ ] High-risk actions have agent restrictions
- [ ] Rate limits on all write/modify operations
- [ ] Regex patterns are specific, not overly broad
- [ ] Critical actions have multiple constraints
- [ ] Policies are versioned and documented
- [ ] Regular audits scheduled
- [ ] Rollback procedure documented

## Further Reading

- [Quickstart Guide](quickstart.md) - Get started in 10 minutes
- [Policy Guide](policy-guide.md) - Complete policy reference
- [Migration Guide](migration-guide.md) - Add to existing agents
- [Troubleshooting](troubleshooting.md) - Common issues
