/**
 * Express.js Middleware Example
 *
 * This example demonstrates how to integrate AI Agent Filter
 * as Express.js middleware to protect API endpoints.
 *
 * To run:
 *   1. npm install express @types/express
 *   2. Start the AI Agent Filter server: docker-compose up -d
 *   3. Run: npx tsx examples/express-middleware.ts
 *   4. Test: curl -X POST http://localhost:3000/api/payment -H "Content-Type: application/json" -d '{"amount": 100}'
 */

import {
  AIFirewall,
  ActionBlockedError,
  NetworkError,
  AIFirewallError,
} from "../src/index.js";

// Note: In a real project, you'd install express
// import express from "express";
// For this example, we'll simulate the types
type Request = {
  body: Record<string, unknown>;
  headers: Record<string, string | undefined>;
  ip?: string;
  method: string;
  path: string;
};
type Response = {
  status: (code: number) => Response;
  json: (data: unknown) => void;
};
type NextFunction = (error?: Error) => void;

// Initialize the AI Firewall client
const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_API_KEY || "af_test_key",
  projectId: "express-api",
  baseUrl: process.env.AI_FIREWALL_URL || "http://localhost:8000",
  strict: true, // Throw on blocked actions
  maxRetries: 2, // Quick retries for API context
  retryBaseDelay: 100,
});

/**
 * Factory function to create validation middleware for specific actions
 *
 * @param actionType - The action type to validate
 * @param extractParams - Optional function to extract params from request
 */
function validateAction(
  actionType: string,
  extractParams?: (req: Request) => Record<string, unknown>
) {
  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      // Get agent name from header or use default
      const agentName = req.headers["x-agent-name"] || "api-client";

      // Extract parameters (default: use request body)
      const params = extractParams
        ? extractParams(req)
        : {
            ...req.body,
            _meta: {
              ip: req.ip,
              method: req.method,
              path: req.path,
            },
          };

      // Validate the action
      await fw.execute(agentName, actionType, params);

      // Action allowed - continue to handler
      next();
    } catch (error) {
      if (error instanceof ActionBlockedError) {
        // Action blocked by policy
        res.status(403).json({
          error: "Action blocked by security policy",
          reason: error.reason,
          actionId: error.actionId,
        });
      } else if (error instanceof NetworkError) {
        // AI Agent Filter server unreachable
        // Depending on your fail-closed preference:

        // Option 1: Fail closed (recommended for security)
        res.status(503).json({
          error: "Security validation unavailable",
          message: "Please try again later",
        });

        // Option 2: Fail open (if availability is priority)
        // console.warn("AI Agent Filter unavailable, allowing request");
        // next();
      } else if (error instanceof AIFirewallError) {
        // Other API errors
        res.status(500).json({
          error: "Security validation error",
          message: error.message,
        });
      } else {
        // Unknown error - pass to error handler
        next(error as Error);
      }
    }
  };
}

/**
 * Middleware to validate all requests with dynamic action type
 */
function validateAllRequests() {
  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      const agentName = req.headers["x-agent-name"] || "api-client";
      const actionType = `${req.method.toLowerCase()}_${req.path.replace(/\//g, "_")}`;

      await fw.execute(agentName, actionType, {
        method: req.method,
        path: req.path,
        body: req.body,
      });

      next();
    } catch (error) {
      if (error instanceof ActionBlockedError) {
        res.status(403).json({
          error: "Request blocked",
          reason: error.reason,
        });
      } else {
        next(error as Error);
      }
    }
  };
}

// =========================================
// Example Usage with Express
// =========================================

async function setupServer() {
  // First, set up the policy
  await fw.updatePolicy({
    name: "api-policy",
    version: "1.0",
    default: "block",
    rules: [
      {
        // Allow creating payments up to $10,000
        action_type: "create_payment",
        effect: "allow",
        constraints: {
          "params.amount": { min: 1, max: 10000 },
          "params.currency": { in: ["USD", "EUR", "GBP"] },
        },
        rate_limit: {
          max_requests: 100,
          window_seconds: 3600,
        },
      },
      {
        // Allow listing payments
        action_type: "list_payments",
        effect: "allow",
        rate_limit: {
          max_requests: 1000,
          window_seconds: 3600,
        },
      },
      {
        // Allow reading user profile
        action_type: "get_user",
        effect: "allow",
      },
      {
        // Allow updating user profile with restrictions
        action_type: "update_user",
        effect: "allow",
        constraints: {
          // Can't change role to admin
          "params.role": { not_in: ["admin", "superuser"] },
        },
      },
    ],
  });

  console.log("📋 Policy configured for API\n");

  // In a real Express app:
  /*
  const app = express();
  app.use(express.json());

  // Protected routes with specific action validation
  app.post("/api/payments",
    validateAction("create_payment"),
    createPaymentHandler
  );

  app.get("/api/payments",
    validateAction("list_payments"),
    listPaymentsHandler
  );

  app.get("/api/users/:id",
    validateAction("get_user", (req) => ({ userId: req.params.id })),
    getUserHandler
  );

  app.patch("/api/users/:id",
    validateAction("update_user", (req) => ({
      userId: req.params.id,
      ...req.body,
    })),
    updateUserHandler
  );

  // Or use blanket validation for all routes
  app.use("/api/admin", validateAllRequests());

  app.listen(3000, () => {
    console.log("Server running on port 3000");
  });
  */
}

// =========================================
// Simulate API Requests
// =========================================

async function simulateRequests() {
  console.log("🧪 Simulating API requests...\n");

  // Simulate allowed payment
  console.log("1️⃣  POST /api/payments (amount: $500)");
  const paymentResult = await fw.execute("api-client", "create_payment", {
    amount: 500,
    currency: "USD",
    recipient: "vendor@example.com",
  });
  console.log(`   ${paymentResult.allowed ? "✅ Allowed" : "❌ Blocked"}\n`);

  // Simulate blocked payment (over limit)
  console.log("2️⃣  POST /api/payments (amount: $50,000)");
  const largePayment = await fw.execute("api-client", "create_payment", {
    amount: 50000,
    currency: "USD",
  });
  console.log(`   ${largePayment.allowed ? "✅ Allowed" : `❌ Blocked: ${largePayment.reason}`}\n`);

  // Simulate blocked admin escalation
  console.log("3️⃣  PATCH /api/users/123 (role: admin)");
  const adminEscalation = await fw.execute("api-client", "update_user", {
    userId: "123",
    role: "admin",
  });
  console.log(`   ${adminEscalation.allowed ? "✅ Allowed" : `❌ Blocked: ${adminEscalation.reason}`}\n`);

  // Simulate blocked undefined action
  console.log("4️⃣  DELETE /api/users/123 (not in policy)");
  const deleteUser = await fw.execute("api-client", "delete_user", {
    userId: "123",
  });
  console.log(`   ${deleteUser.allowed ? "✅ Allowed" : `❌ Blocked: ${deleteUser.reason}`}\n`);
}

async function main() {
  console.log("🔥 AI Agent Filter - Express.js Middleware Example\n");

  await setupServer();
  await simulateRequests();

  // Show stats
  const stats = await fw.getStats();
  console.log("📊 Statistics:");
  console.log(`   Total requests: ${stats.totalActions}`);
  console.log(`   Allowed: ${stats.allowed}`);
  console.log(`   Blocked: ${stats.blocked}`);
  console.log(`   Block rate: ${stats.blockRate.toFixed(1)}%`);

  console.log("\n✨ Example complete!");
}

main().catch(console.error);
