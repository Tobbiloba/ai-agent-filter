# AI Agent Filter - Node.js SDK

[![npm version](https://img.shields.io/npm/v/@ai-agent-filter/sdk.svg)](https://www.npmjs.com/package/@ai-agent-filter/sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js Version](https://img.shields.io/node/v/@ai-agent-filter/sdk.svg)](https://nodejs.org)

The official Node.js/TypeScript SDK for [AI Agent Filter](https://aiagentfilter.com) - validate AI agent actions against security policies before execution.

**AI Agent Filter** is an open-source guardrails system that sits between your AI agents and the actions they perform. It validates every action against configurable policies, enforces rate limits, and provides complete audit logging.

## Why AI Agent Filter?

- **80% of organizations** have encountered risky behaviors from AI agents
- **23% of IT professionals** have witnessed agents deceived into revealing credentials
- **OWASP ranks prompt injection** as the #1 security risk for LLM applications in 2025

AI Agent Filter helps you:
- **Prevent unauthorized actions** - Block agents from exceeding spending limits, accessing forbidden resources, or performing dangerous operations
- **Enforce rate limits** - Prevent runaway agents from making unlimited API calls or transactions
- **Audit everything** - Complete audit trail of every action for compliance and debugging
- **Simulate policies** - Test policy changes without affecting production

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Core Concepts](#core-concepts)
- [API Reference](#api-reference)
- [Error Handling](#error-handling)
- [Framework Integrations](#framework-integrations)
- [Advanced Usage](#advanced-usage)
- [TypeScript Support](#typescript-support)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Installation

```bash
npm install @ai-agent-filter/sdk
```

**Requirements:**
- Node.js 18+ (uses native `fetch`)
- TypeScript 5.0+ (optional, for type definitions)

---

## Quick Start

### 1. Start the AI Agent Filter Server

```bash
# Using Docker (recommended)
docker run -p 8000:8000 aiagentfilter/server:latest

# Or with docker-compose
docker-compose up -d
```

### 2. Create a Project and Get an API Key

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project", "description": "My AI agent project"}'
```

### 3. Validate Agent Actions

```typescript
import { AIFirewall } from "@ai-agent-filter/sdk";

// Initialize the client
const fw = new AIFirewall({
  apiKey: "af_your_api_key",
  projectId: "my-project",
  baseUrl: "http://localhost:8000", // Your AI Agent Filter server
});

// Validate an action before executing
const result = await fw.execute("invoice_agent", "pay_invoice", {
  vendor: "Acme Corp",
  amount: 5000,
  currency: "USD",
});

if (result.allowed) {
  console.log(`✅ Action allowed (ID: ${result.actionId})`);
  // Proceed with the actual payment
  await processPayment({ vendor: "Acme Corp", amount: 5000 });
} else {
  console.log(`❌ Action blocked: ${result.reason}`);
  // Handle the blocked action (notify user, log, etc.)
}
```

---

## Configuration

### Client Options

```typescript
const fw = new AIFirewall({
  // Required
  apiKey: "af_xxx",              // Your project API key
  projectId: "my-project",       // Your project identifier

  // Optional - Server
  baseUrl: "http://localhost:8000",  // API URL (default: http://localhost:8000)
  timeout: 30000,                    // Request timeout in ms (default: 30000)

  // Optional - Behavior
  strict: false,                 // Throw ActionBlockedError when blocked (default: false)

  // Optional - Retry Configuration
  maxRetries: 3,                 // Max retry attempts (default: 3, set to 0 to disable)
  retryBaseDelay: 1000,          // Base delay in ms for exponential backoff (default: 1000)
  retryMaxDelay: 30000,          // Maximum delay cap in ms (default: 30000)
  retryOnStatus: [429, 500, 502, 503, 504],  // HTTP codes to retry (default)
  retryOnNetworkError: true,     // Retry on network failures (default: true)
});
```

### Environment Variables

You can also configure the client using environment variables:

```bash
AI_FIREWALL_API_KEY=af_your_api_key
AI_FIREWALL_PROJECT_ID=my-project
AI_FIREWALL_BASE_URL=http://localhost:8000
```

```typescript
const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_API_KEY!,
  projectId: process.env.AI_FIREWALL_PROJECT_ID!,
  baseUrl: process.env.AI_FIREWALL_BASE_URL,
});
```

---

## Core Concepts

### Actions

An **action** is any operation your AI agent wants to perform. Actions have:
- **Agent Name**: Identifier for the agent (e.g., `"invoice_agent"`, `"support_bot"`)
- **Action Type**: The operation type (e.g., `"pay_invoice"`, `"send_email"`, `"delete_file"`)
- **Parameters**: Key-value pairs with action details (e.g., `{ amount: 5000, currency: "USD" }`)

### Policies

A **policy** defines what actions are allowed. Policies contain rules that specify:
- Which actions are allowed/blocked
- Parameter constraints (min/max values, allowed values, regex patterns)
- Rate limits (requests per time window)
- Aggregate limits (total amounts over time)

Example policy:
```json
{
  "name": "finance-policy",
  "version": "1.0",
  "default": "block",
  "rules": [
    {
      "action_type": "pay_invoice",
      "effect": "allow",
      "constraints": {
        "params.amount": { "max": 10000 },
        "params.currency": { "in": ["USD", "EUR", "GBP"] }
      },
      "rate_limit": {
        "max_requests": 100,
        "window_seconds": 3600
      }
    }
  ]
}
```

### Validation Flow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  AI Agent   │────▶│  AI Agent Filter │────▶│   Action    │
│             │     │    (Validate)    │     │ (If allowed)│
└─────────────┘     └──────────────────┘     └─────────────┘
                            │
                            ▼
                    ┌──────────────────┐
                    │   Audit Log      │
                    └──────────────────┘
```

---

## API Reference

### `execute(agentName, actionType, params?, options?)`

Validate an action before executing it.

```typescript
const result = await fw.execute(
  "agent_name",      // Agent identifier
  "action_type",     // Action type
  { key: "value" },  // Parameters (optional)
  { simulate: false } // Options (optional)
);
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agentName` | `string` | Yes | Identifier for the agent |
| `actionType` | `string` | Yes | Type of action being performed |
| `params` | `Record<string, unknown>` | No | Action parameters (default: `{}`) |
| `options.simulate` | `boolean` | No | If true, validate without logging (default: `false`) |

**Returns:** `Promise<ValidationResult>`

```typescript
interface ValidationResult {
  allowed: boolean;           // Whether the action is allowed
  actionId: string | null;    // Unique ID (null for simulations)
  timestamp: Date;            // When validation occurred
  reason?: string;            // Reason if blocked
  executionTimeMs?: number;   // Validation time in ms
  simulated: boolean;         // Whether this was a simulation
}
```

**Example:**
```typescript
// Basic validation
const result = await fw.execute("bot", "send_email", {
  to: "user@example.com",
  subject: "Hello",
});

// Simulation (what-if mode)
const simResult = await fw.execute("bot", "delete_account", { userId: "123" }, { simulate: true });
if (!simResult.allowed) {
  console.log(`Would be blocked: ${simResult.reason}`);
}
```

---

### `getPolicy()`

Get the active policy for your project.

```typescript
const policy = await fw.getPolicy();
```

**Returns:** `Promise<Policy>`

```typescript
interface Policy {
  id: number;              // Policy database ID
  projectId: string;       // Associated project
  name: string;            // Policy name
  version: string;         // Policy version
  rules: Record<string, unknown>;  // Policy rules
  isActive: boolean;       // Whether this policy is active
  createdAt: Date;         // Creation timestamp
  updatedAt: Date;         // Last update timestamp
}
```

**Example:**
```typescript
const policy = await fw.getPolicy();
console.log(`Active policy: ${policy.name} v${policy.version}`);
console.log(`Rules: ${JSON.stringify(policy.rules, null, 2)}`);
```

---

### `updatePolicy(options)`

Update the policy for your project.

```typescript
const policy = await fw.updatePolicy({
  rules: [...],
  name: "my-policy",
  version: "2.0",
  default: "block",
});
```

**Parameters:**

```typescript
interface UpdatePolicyOptions {
  rules: Array<Record<string, unknown>>;  // Policy rules (required)
  name?: string;           // Policy name (default: "default")
  version?: string;        // Version string (default: "1.0")
  default?: "allow" | "block";  // Default behavior (default: "allow")
}
```

**Returns:** `Promise<Policy>`

**Example:**
```typescript
const policy = await fw.updatePolicy({
  name: "production-policy",
  version: "2.0",
  default: "block",
  rules: [
    {
      action_type: "pay_invoice",
      effect: "allow",
      constraints: {
        "params.amount": { max: 10000 },
        "params.currency": { in: ["USD", "EUR"] },
      },
      rate_limit: {
        max_requests: 50,
        window_seconds: 3600,
      },
    },
    {
      action_type: "send_email",
      effect: "allow",
      constraints: {
        "params.to": { pattern: "^[\\w.-]+@company\\.com$" },
      },
    },
    {
      action_type: "*",
      effect: "allow",
      rate_limit: {
        max_requests: 1000,
        window_seconds: 86400,
      },
    },
  ],
});
```

---

### `getLogs(options?)`

Get audit logs for your project.

```typescript
const logs = await fw.getLogs({
  page: 1,
  pageSize: 50,
  agentName: "invoice_agent",
  allowed: false,
});
```

**Parameters:**

```typescript
interface GetLogsOptions {
  page?: number;           // Page number, 1-indexed (default: 1)
  pageSize?: number;       // Items per page (default: 50, max: 100)
  agentName?: string;      // Filter by agent name
  actionType?: string;     // Filter by action type
  allowed?: boolean;       // Filter by allowed status
}
```

**Returns:** `Promise<LogsPage>`

```typescript
interface LogsPage {
  items: AuditLogEntry[];  // Log entries
  total: number;           // Total count
  page: number;            // Current page
  pageSize: number;        // Items per page
  hasMore: boolean;        // More pages available
}

interface AuditLogEntry {
  actionId: string;
  projectId: string;
  agentName: string;
  actionType: string;
  params: Record<string, unknown>;
  allowed: boolean;
  reason?: string;
  policyVersion?: string;
  executionTimeMs?: number;
  timestamp: Date;
}
```

**Example:**
```typescript
// Get all blocked actions
const blockedLogs = await fw.getLogs({ allowed: false });

for (const entry of blockedLogs.items) {
  console.log(`[${entry.timestamp.toISOString()}] ${entry.agentName}/${entry.actionType}: ${entry.reason}`);
}

// Paginate through all logs
let page = 1;
let hasMore = true;
while (hasMore) {
  const logs = await fw.getLogs({ page, pageSize: 100 });
  processLogs(logs.items);
  hasMore = logs.hasMore;
  page++;
}
```

---

### `getStats()`

Get validation statistics for your project.

```typescript
const stats = await fw.getStats();
```

**Returns:** `Promise<Stats>`

```typescript
interface Stats {
  totalActions: number;    // Total validations
  allowed: number;         // Allowed count
  blocked: number;         // Blocked count
  blockRate: number;       // Block percentage (0-100)
  topActionTypes?: Array<{ actionType: string; count: number }>;
  topAgents?: Array<{ agentName: string; count: number }>;
}
```

**Example:**
```typescript
const stats = await fw.getStats();

console.log(`Total actions: ${stats.totalActions}`);
console.log(`Allowed: ${stats.allowed} (${100 - stats.blockRate}%)`);
console.log(`Blocked: ${stats.blocked} (${stats.blockRate}%)`);

console.log("\nTop action types:");
stats.topActionTypes?.forEach(({ actionType, count }) => {
  console.log(`  ${actionType}: ${count}`);
});
```

---

### `close()`

Close the client. This is a no-op for the fetch-based client but included for API parity with the Python SDK.

```typescript
fw.close();
```

---

## Error Handling

### Error Classes

The SDK provides specific error classes for different failure scenarios:

```typescript
import {
  AIFirewall,
  AIFirewallError,        // Base error class
  AuthenticationError,    // Invalid or missing API key (401/403)
  ProjectNotFoundError,   // Project doesn't exist (404)
  PolicyNotFoundError,    // No active policy (404)
  ValidationError,        // Invalid request format (422)
  RateLimitError,         // Rate limit exceeded (429)
  NetworkError,           // Connection failed or timeout
  ActionBlockedError,     // Action blocked (strict mode only)
} from "@ai-agent-filter/sdk";
```

### Handling Errors

```typescript
try {
  const result = await fw.execute("agent", "action", params);
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error("Invalid API key - check your credentials");
  } else if (error instanceof PolicyNotFoundError) {
    console.error("No policy configured - create one first");
  } else if (error instanceof RateLimitError) {
    console.error("Rate limited - slow down requests");
  } else if (error instanceof NetworkError) {
    console.error("Network error - check server connectivity");
  } else if (error instanceof ActionBlockedError) {
    console.error(`Action blocked: ${error.reason} (ID: ${error.actionId})`);
  } else if (error instanceof AIFirewallError) {
    console.error(`API error: ${error.message}`);
  } else {
    throw error; // Unknown error
  }
}
```

### Strict Mode

When `strict: true`, blocked actions throw `ActionBlockedError` instead of returning a result:

```typescript
const fw = new AIFirewall({
  apiKey: "af_xxx",
  projectId: "my-project",
  strict: true,
});

try {
  // This will throw if the action is blocked
  const result = await fw.execute("agent", "dangerous_action", { amount: 1000000 });
  // Only reached if action is allowed
  await performAction();
} catch (error) {
  if (error instanceof ActionBlockedError) {
    console.log(`Blocked: ${error.reason}`);
    console.log(`Action ID: ${error.actionId}`);
  }
}
```

**Note:** Simulations never throw `ActionBlockedError` even in strict mode.

---

## Framework Integrations

### LangChain.js

```typescript
import { AIFirewall, ActionBlockedError } from "@ai-agent-filter/sdk";
import { Tool } from "@langchain/core/tools";

const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_API_KEY!,
  projectId: "langchain-agent",
});

// Wrap any tool with validation
function withFirewall<T extends Tool>(tool: T, agentName: string): T {
  const originalCall = tool._call.bind(tool);

  tool._call = async (input: string) => {
    const result = await fw.execute(agentName, tool.name, { input });

    if (!result.allowed) {
      return `Action blocked by security policy: ${result.reason}`;
    }

    return originalCall(input);
  };

  return tool;
}

// Usage
const calculator = withFirewall(new CalculatorTool(), "math-agent");
```

### Vercel AI SDK

```typescript
import { AIFirewall } from "@ai-agent-filter/sdk";
import { generateText, tool } from "ai";
import { z } from "zod";

const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_API_KEY!,
  projectId: "vercel-ai-agent",
});

const sendEmail = tool({
  description: "Send an email",
  parameters: z.object({
    to: z.string().email(),
    subject: z.string(),
    body: z.string(),
  }),
  execute: async ({ to, subject, body }) => {
    // Validate before executing
    const validation = await fw.execute("email-agent", "send_email", {
      to,
      subject,
      bodyLength: body.length,
    });

    if (!validation.allowed) {
      throw new Error(`Blocked: ${validation.reason}`);
    }

    // Proceed with sending email
    return await emailService.send({ to, subject, body });
  },
});
```

### Express.js Middleware

```typescript
import express from "express";
import { AIFirewall, ActionBlockedError } from "@ai-agent-filter/sdk";

const app = express();
const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_API_KEY!,
  projectId: "api-server",
  strict: true,
});

// Middleware to validate agent actions
const validateAction = (actionType: string) => {
  return async (req: express.Request, res: express.Response, next: express.NextFunction) => {
    try {
      const agentName = req.headers["x-agent-name"] as string || "unknown";

      await fw.execute(agentName, actionType, {
        ...req.body,
        ip: req.ip,
        userAgent: req.headers["user-agent"],
      });

      next();
    } catch (error) {
      if (error instanceof ActionBlockedError) {
        res.status(403).json({
          error: "Action blocked by policy",
          reason: error.reason,
          actionId: error.actionId,
        });
      } else {
        next(error);
      }
    }
  };
};

// Protected routes
app.post("/api/payments", validateAction("create_payment"), createPaymentHandler);
app.delete("/api/users/:id", validateAction("delete_user"), deleteUserHandler);
```

### Next.js API Routes

```typescript
// app/api/agent/route.ts
import { NextRequest, NextResponse } from "next/server";
import { AIFirewall } from "@ai-agent-filter/sdk";

const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_API_KEY!,
  projectId: "nextjs-app",
});

export async function POST(request: NextRequest) {
  const { agentName, action, params } = await request.json();

  const validation = await fw.execute(agentName, action, params);

  if (!validation.allowed) {
    return NextResponse.json(
      { error: "Action blocked", reason: validation.reason },
      { status: 403 }
    );
  }

  // Execute the action
  const result = await executeAgentAction(action, params);

  return NextResponse.json({ success: true, result, actionId: validation.actionId });
}
```

---

## Advanced Usage

### Simulation Mode (What-If Testing)

Test whether an action would be allowed without creating an audit log entry:

```typescript
// Test a potentially dangerous action
const simResult = await fw.execute(
  "test-agent",
  "delete_all_data",
  { confirm: true },
  { simulate: true }
);

if (simResult.allowed) {
  console.log("Warning: This action would be allowed!");
} else {
  console.log(`Good: This action would be blocked (${simResult.reason})`);
}

// simResult.actionId is null for simulations
// simResult.simulated is true
```

### Retry Configuration

The SDK automatically retries on transient failures with exponential backoff:

```typescript
const fw = new AIFirewall({
  apiKey: "af_xxx",
  projectId: "my-project",

  // Retry configuration
  maxRetries: 5,                    // Try up to 6 times total
  retryBaseDelay: 500,              // Start with 500ms delay
  retryMaxDelay: 60000,             // Max 60s between retries
  retryOnStatus: [429, 500, 502, 503, 504],  // Retry these status codes
  retryOnNetworkError: true,        // Retry on connection failures
});

// Disable retries for time-sensitive operations
const fwNoRetry = new AIFirewall({
  apiKey: "af_xxx",
  projectId: "my-project",
  maxRetries: 0,  // Fail immediately
});
```

### Bulk Validation

For validating multiple actions efficiently:

```typescript
async function validateBatch(actions: Array<{ agent: string; type: string; params: any }>) {
  const results = await Promise.all(
    actions.map(({ agent, type, params }) =>
      fw.execute(agent, type, params).catch(err => ({
        allowed: false,
        reason: err.message,
        error: true
      }))
    )
  );

  const blocked = results.filter(r => !r.allowed);
  if (blocked.length > 0) {
    console.log(`${blocked.length}/${results.length} actions would be blocked`);
  }

  return results;
}
```

### Monitoring and Metrics

```typescript
import { AIFirewall } from "@ai-agent-filter/sdk";

class MonitoredFirewall {
  private fw: AIFirewall;
  private metrics = {
    total: 0,
    allowed: 0,
    blocked: 0,
    errors: 0,
    totalLatencyMs: 0,
  };

  constructor(options: AIFirewallOptions) {
    this.fw = new AIFirewall(options);
  }

  async execute(...args: Parameters<AIFirewall["execute"]>) {
    const start = Date.now();
    this.metrics.total++;

    try {
      const result = await this.fw.execute(...args);
      this.metrics.totalLatencyMs += Date.now() - start;

      if (result.allowed) {
        this.metrics.allowed++;
      } else {
        this.metrics.blocked++;
      }

      return result;
    } catch (error) {
      this.metrics.errors++;
      this.metrics.totalLatencyMs += Date.now() - start;
      throw error;
    }
  }

  getMetrics() {
    return {
      ...this.metrics,
      avgLatencyMs: this.metrics.total > 0
        ? this.metrics.totalLatencyMs / this.metrics.total
        : 0,
      blockRate: this.metrics.total > 0
        ? (this.metrics.blocked / this.metrics.total) * 100
        : 0,
    };
  }
}
```

---

## TypeScript Support

The SDK is written in TypeScript and provides full type definitions:

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
  ExecuteOptions,
} from "@ai-agent-filter/sdk";

// All types are exported and available
const options: AIFirewallOptions = {
  apiKey: "af_xxx",
  projectId: "my-project",
  strict: true,
};

const handleResult = (result: ValidationResult) => {
  if (result.allowed) {
    console.log(`Allowed: ${result.actionId}`);
  }
};
```

---

## Examples

### Complete Example: Payment Agent

```typescript
import { AIFirewall, ActionBlockedError } from "@ai-agent-filter/sdk";

// Initialize client
const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_API_KEY!,
  projectId: "payment-system",
  strict: true,
});

// Set up policy
await fw.updatePolicy({
  name: "payment-policy",
  version: "1.0",
  default: "block",
  rules: [
    {
      action_type: "create_payment",
      effect: "allow",
      constraints: {
        "params.amount": { min: 1, max: 50000 },
        "params.currency": { in: ["USD", "EUR", "GBP"] },
      },
      rate_limit: {
        max_requests: 100,
        window_seconds: 3600,
      },
      aggregate_limit: {
        field: "params.amount",
        max: 100000,
        window_seconds: 86400,
      },
    },
    {
      action_type: "refund_payment",
      effect: "allow",
      constraints: {
        "params.amount": { max: 10000 },
      },
    },
  ],
});

// Payment processing function
async function processPayment(agent: string, amount: number, currency: string, recipient: string) {
  try {
    // Validate with AI Agent Filter
    const validation = await fw.execute(agent, "create_payment", {
      amount,
      currency,
      recipient,
    });

    console.log(`✅ Payment validated (ID: ${validation.actionId})`);

    // Actually process the payment
    const paymentResult = await paymentGateway.charge({
      amount,
      currency,
      recipient,
    });

    return { success: true, paymentId: paymentResult.id, validationId: validation.actionId };

  } catch (error) {
    if (error instanceof ActionBlockedError) {
      console.log(`❌ Payment blocked: ${error.reason}`);
      return { success: false, error: error.reason, actionId: error.actionId };
    }
    throw error;
  }
}

// Usage
const result = await processPayment("invoice-bot", 5000, "USD", "vendor@example.com");
```

### Complete Example: Multi-Agent System

```typescript
import { AIFirewall } from "@ai-agent-filter/sdk";

const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_API_KEY!,
  projectId: "multi-agent-system",
});

// Different agents with different permissions
const agents = {
  reader: {
    name: "reader-agent",
    actions: ["read_file", "list_directory", "search"],
  },
  writer: {
    name: "writer-agent",
    actions: ["read_file", "write_file", "create_file"],
  },
  admin: {
    name: "admin-agent",
    actions: ["*"],
  },
};

// Validate agent action
async function agentAction(
  agentType: keyof typeof agents,
  actionType: string,
  params: Record<string, unknown>
) {
  const agent = agents[agentType];

  const result = await fw.execute(agent.name, actionType, params);

  if (!result.allowed) {
    throw new Error(`Agent ${agent.name} is not allowed to ${actionType}: ${result.reason}`);
  }

  return result;
}

// Usage
await agentAction("reader", "read_file", { path: "/data/report.txt" });  // ✅ Allowed
await agentAction("reader", "delete_file", { path: "/data/report.txt" }); // ❌ Blocked
```

---

## Troubleshooting

### Common Issues

#### "Connection refused" error
Make sure the AI Agent Filter server is running:
```bash
curl http://localhost:8000/health
```

#### "Invalid API key" error
Check that your API key is correct and starts with `af_`:
```typescript
console.log(process.env.AI_FIREWALL_API_KEY); // Should start with 'af_'
```

#### "No active policy" error
Create a policy for your project:
```typescript
await fw.updatePolicy({
  rules: [{ action_type: "*", effect: "allow" }],
});
```

#### Timeout errors
Increase the timeout or check network connectivity:
```typescript
const fw = new AIFirewall({
  ...options,
  timeout: 60000, // 60 seconds
});
```

### Debug Mode

Enable debug logging by checking the request/response:

```typescript
// Check what's being sent
const result = await fw.execute("agent", "action", { debug: true });
console.log(JSON.stringify(result, null, 2));

// Check audit logs
const logs = await fw.getLogs({ pageSize: 1 });
console.log(logs.items[0]);
```

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](https://github.com/ai-agent-filter/ai-agent-filter/blob/main/CONTRIBUTING.md).

```bash
# Clone the repo
git clone https://github.com/ai-agent-filter/ai-agent-filter.git
cd ai-agent-filter/sdk/nodejs

# Install dependencies
npm install

# Run tests
npm test

# Build
npm run build
```

---

## License

MIT License - see [LICENSE](./LICENSE) for details.

---

## Links

- [Documentation](https://docs.aiagentfilter.com)
- [GitHub Repository](https://github.com/ai-agent-filter/ai-agent-filter)
- [Python SDK](https://pypi.org/project/ai-firewall/)
- [Discord Community](https://discord.gg/aiagentfilter)
- [Twitter](https://twitter.com/aiagentfilter)

---

<p align="center">
  <strong>AI Agent Filter</strong> - Guardrails for AI Agents
  <br>
  <a href="https://aiagentfilter.com">Website</a> •
  <a href="https://github.com/ai-agent-filter/ai-agent-filter">GitHub</a> •
  <a href="https://docs.aiagentfilter.com">Docs</a>
</p>
