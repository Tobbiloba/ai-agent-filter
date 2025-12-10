# AI Firewall Node.js SDK

Node.js/TypeScript SDK for the AI Agent Safety Filter. Validate AI agent actions against policies before execution.

## Installation

```bash
npm install ai-firewall
```

**Requirements:** Node.js 18+ (uses native `fetch`)

## Quick Start

```typescript
import { AIFirewall } from "ai-firewall";

const fw = new AIFirewall({
  apiKey: "af_your_api_key",
  projectId: "my-project",
  baseUrl: "http://localhost:8000", // optional
});

// Validate an action before executing
const result = await fw.execute("invoice_agent", "pay_invoice", {
  vendor: "Acme Corp",
  amount: 5000,
  currency: "USD",
});

if (result.allowed) {
  console.log(`Action allowed: ${result.actionId}`);
  // Proceed with payment
} else {
  console.log(`Blocked: ${result.reason}`);
}
```

## Configuration

```typescript
const fw = new AIFirewall({
  apiKey: "af_xxx",           // Required: Your project API key
  projectId: "my-project",    // Required: Your project ID
  baseUrl: "http://...",      // Optional: API URL (default: http://localhost:8000)
  timeout: 30000,             // Optional: Request timeout in ms (default: 30000)
  strict: false,              // Optional: Throw on blocked actions (default: false)
});
```

## Strict Mode

When `strict: true`, blocked actions throw an exception instead of returning a result:

```typescript
import { AIFirewall, ActionBlockedError } from "ai-firewall";

const fw = new AIFirewall({
  apiKey: "af_xxx",
  projectId: "my-project",
  strict: true,
});

try {
  const result = await fw.execute("agent", "risky_action", { amount: 1000000 });
  // Only reached if action is allowed
  processPayment();
} catch (error) {
  if (error instanceof ActionBlockedError) {
    console.log(`Blocked: ${error.reason}`);
    console.log(`Action ID: ${error.actionId}`);
  }
}
```

## API Reference

### `execute(agentName, actionType, params?)`

Validate an action before executing it.

```typescript
const result = await fw.execute("agent_name", "action_type", { key: "value" });

// Result:
// {
//   allowed: boolean,
//   actionId: string,
//   timestamp: Date,
//   reason?: string,        // Only if blocked
//   executionTimeMs?: number
// }
```

### `getPolicy()`

Get the active policy for your project.

```typescript
const policy = await fw.getPolicy();

console.log(`Policy: ${policy.name} v${policy.version}`);
console.log(`Active: ${policy.isActive}`);
console.log(`Rules: ${JSON.stringify(policy.rules)}`);
```

### `updatePolicy(options)`

Update the policy for your project.

```typescript
const policy = await fw.updatePolicy({
  name: "invoice-policy",
  version: "2.0",
  default: "block",
  rules: [
    {
      action_type: "pay_invoice",
      constraints: {
        "params.amount": { max: 10000 },
        "params.currency": { in: ["USD", "EUR"] },
      },
    },
    {
      action_type: "*",
      rate_limit: { max_requests: 100, window_seconds: 3600 },
    },
  ],
});
```

### `getLogs(options?)`

Get audit logs for your project.

```typescript
// Get all logs
const logs = await fw.getLogs();

// With filters
const blockedLogs = await fw.getLogs({
  page: 1,
  pageSize: 50,
  agentName: "invoice_agent",
  actionType: "pay_invoice",
  allowed: false,
});

for (const entry of blockedLogs.items) {
  console.log(`${entry.actionType}: ${entry.reason}`);
}

// Check for more pages
if (logs.hasMore) {
  const nextPage = await fw.getLogs({ page: 2 });
}
```

### `getStats()`

Get audit statistics for your project.

```typescript
const stats = await fw.getStats();

console.log(`Total actions: ${stats.totalActions}`);
console.log(`Allowed: ${stats.allowed}`);
console.log(`Blocked: ${stats.blocked}`);
console.log(`Block rate: ${stats.blockRate}%`);
```

### `close()`

Close the client (no-op for fetch-based client, included for API parity).

```typescript
fw.close();
```

## Error Handling

```typescript
import {
  AIFirewall,
  AIFirewallError,
  AuthenticationError,
  ProjectNotFoundError,
  PolicyNotFoundError,
  ValidationError,
  NetworkError,
  ActionBlockedError,
} from "ai-firewall";

try {
  const result = await fw.execute("agent", "action", {});
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.log("Invalid API key");
  } else if (error instanceof PolicyNotFoundError) {
    console.log("No active policy");
  } else if (error instanceof NetworkError) {
    console.log("Network error or timeout");
  } else if (error instanceof ActionBlockedError) {
    console.log(`Blocked: ${error.reason}`);
  } else if (error instanceof AIFirewallError) {
    console.log(`API error: ${error.message}`);
  }
}
```

### Error Types

| Error | Description |
|-------|-------------|
| `AIFirewallError` | Base error class |
| `AuthenticationError` | Invalid or missing API key |
| `ProjectNotFoundError` | Project doesn't exist |
| `PolicyNotFoundError` | No active policy for project |
| `ValidationError` | Invalid request format |
| `RateLimitError` | Rate limit exceeded |
| `NetworkError` | Connection failed or timed out |
| `ActionBlockedError` | Action blocked (strict mode only) |

## TypeScript Support

Full TypeScript support with exported types:

```typescript
import type {
  AIFirewallOptions,
  ValidationResult,
  Policy,
  AuditLogEntry,
  LogsPage,
  Stats,
  UpdatePolicyOptions,
  GetLogsOptions,
} from "ai-firewall";
```

## Framework Integration Examples

### Express.js Middleware

```typescript
import { AIFirewall, ActionBlockedError } from "ai-firewall";

const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_KEY!,
  projectId: "my-project",
});

async function validateAction(agentName: string, actionType: string, params: any) {
  const result = await fw.execute(agentName, actionType, params);
  if (!result.allowed) {
    throw new Error(`Action blocked: ${result.reason}`);
  }
  return result;
}

// In your route handler:
app.post("/api/payment", async (req, res) => {
  try {
    await validateAction("payment_agent", "process_payment", req.body);
    // Process payment...
  } catch (error) {
    res.status(403).json({ error: error.message });
  }
});
```

### LangChain Integration

```typescript
import { AIFirewall } from "ai-firewall";

const fw = new AIFirewall({ apiKey: "...", projectId: "..." });

// Wrap tool execution with validation
async function executeToolWithValidation(
  toolName: string,
  args: Record<string, unknown>
) {
  const result = await fw.execute("langchain_agent", toolName, args);

  if (!result.allowed) {
    return `Action blocked: ${result.reason}`;
  }

  // Execute the actual tool
  return executeTool(toolName, args);
}
```

## License

MIT
