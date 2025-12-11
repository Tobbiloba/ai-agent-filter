/**
 * Retry and Error Handling Example
 *
 * This example demonstrates the SDK's retry behavior and
 * comprehensive error handling capabilities.
 *
 * To run:
 *   1. Start the AI Agent Filter server: docker-compose up -d
 *   2. Run: npx tsx examples/retry-and-error-handling.ts
 */

import {
  AIFirewall,
  AIFirewallError,
  AuthenticationError,
  ProjectNotFoundError,
  PolicyNotFoundError,
  ValidationError,
  RateLimitError,
  NetworkError,
  ActionBlockedError,
} from "../src/index.js";

async function main() {
  console.log("🔥 AI Agent Filter - Retry and Error Handling Example\n");

  // =========================================
  // 1. Retry Configuration
  // =========================================
  console.log("1️⃣  Retry Configuration Examples\n");

  // Default retry settings
  const fwDefault = new AIFirewall({
    apiKey: process.env.AI_FIREWALL_API_KEY || "af_test_key",
    projectId: "retry-example",
    baseUrl: process.env.AI_FIREWALL_URL || "http://localhost:8000",
    // Default: maxRetries: 3, retryBaseDelay: 1000
  });

  console.log("   Default config: 3 retries, 1s base delay");

  // Aggressive retries for critical operations
  const fwAggressive = new AIFirewall({
    apiKey: process.env.AI_FIREWALL_API_KEY || "af_test_key",
    projectId: "retry-example",
    baseUrl: process.env.AI_FIREWALL_URL || "http://localhost:8000",
    maxRetries: 5,
    retryBaseDelay: 500,
    retryMaxDelay: 30000,
    retryOnStatus: [429, 500, 502, 503, 504],
    retryOnNetworkError: true,
  });

  console.log("   Aggressive config: 5 retries, 500ms base, max 30s");

  // No retries for time-sensitive operations
  const fwNoRetry = new AIFirewall({
    apiKey: process.env.AI_FIREWALL_API_KEY || "af_test_key",
    projectId: "retry-example",
    baseUrl: process.env.AI_FIREWALL_URL || "http://localhost:8000",
    maxRetries: 0,
  });

  console.log("   No-retry config: immediate failure\n");

  // =========================================
  // 2. Error Handling Patterns
  // =========================================
  console.log("2️⃣  Error Handling Patterns\n");

  // Set up a policy first
  try {
    await fwDefault.updatePolicy({
      name: "error-example-policy",
      version: "1.0",
      default: "block",
      rules: [
        { action_type: "allowed_action", effect: "allow" },
        {
          action_type: "limited_action",
          effect: "allow",
          constraints: { "params.value": { max: 100 } },
        },
      ],
    });
    console.log("   ✅ Policy configured\n");
  } catch (error) {
    console.log(`   ❌ Failed to set up policy: ${error}\n`);
    return;
  }

  // Comprehensive error handling function
  async function safeExecute(
    fw: AIFirewall,
    agent: string,
    action: string,
    params: Record<string, unknown>
  ): Promise<{ success: boolean; result?: unknown; error?: string }> {
    try {
      const result = await fw.execute(agent, action, params);
      return { success: true, result };
    } catch (error) {
      if (error instanceof AuthenticationError) {
        // API key is invalid or missing
        console.log("   ⚠️  Authentication failed - check API key");
        return { success: false, error: "authentication_failed" };
      }

      if (error instanceof ProjectNotFoundError) {
        // Project doesn't exist
        console.log("   ⚠️  Project not found - check project ID");
        return { success: false, error: "project_not_found" };
      }

      if (error instanceof PolicyNotFoundError) {
        // No policy configured
        console.log("   ⚠️  No policy found - create one first");
        return { success: false, error: "policy_not_found" };
      }

      if (error instanceof ValidationError) {
        // Invalid request format
        console.log("   ⚠️  Invalid request - check parameters");
        return { success: false, error: "validation_error" };
      }

      if (error instanceof RateLimitError) {
        // Rate limited by AI Agent Filter
        console.log("   ⚠️  Rate limited - slow down requests");
        return { success: false, error: "rate_limited" };
      }

      if (error instanceof NetworkError) {
        // Connection failed or timeout
        console.log("   ⚠️  Network error - server may be down");
        return { success: false, error: "network_error" };
      }

      if (error instanceof ActionBlockedError) {
        // Action blocked (strict mode)
        console.log(`   ⚠️  Action blocked: ${error.reason}`);
        return { success: false, error: "blocked", result: error.actionId };
      }

      if (error instanceof AIFirewallError) {
        // Other API errors
        console.log(`   ⚠️  API error: ${error.message}`);
        return { success: false, error: "api_error" };
      }

      // Unknown error - rethrow
      throw error;
    }
  }

  // Test various scenarios
  console.log("   Testing allowed action...");
  await safeExecute(fwDefault, "agent", "allowed_action", { data: "test" });

  console.log("   Testing blocked action...");
  await safeExecute(fwDefault, "agent", "blocked_action", { data: "test" });

  console.log("   Testing constraint violation...");
  await safeExecute(fwDefault, "agent", "limited_action", { value: 500 });

  // =========================================
  // 3. Retry Behavior Visualization
  // =========================================
  console.log("\n3️⃣  Retry Timing (Exponential Backoff)\n");

  // Calculate backoff delays
  function calculateBackoff(
    attempt: number,
    baseDelay: number,
    maxDelay: number
  ): number {
    const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
    const jitterRange = delay * 0.25;
    return delay; // Without jitter for display
  }

  const baseDelay = 1000;
  const maxDelay = 30000;

  console.log("   Attempt | Delay    | Cumulative");
  console.log("   --------|----------|------------");

  let cumulative = 0;
  for (let i = 0; i <= 5; i++) {
    const delay = calculateBackoff(i, baseDelay, maxDelay);
    cumulative += delay;
    console.log(
      `   ${i.toString().padStart(7)} | ${(delay / 1000).toFixed(1).padStart(6)}s | ${(cumulative / 1000).toFixed(1).padStart(7)}s`
    );
  }

  // =========================================
  // 4. Circuit Breaker Pattern
  // =========================================
  console.log("\n4️⃣  Circuit Breaker Pattern\n");

  class CircuitBreaker {
    private failures = 0;
    private lastFailure = 0;
    private state: "closed" | "open" | "half-open" = "closed";

    constructor(
      private readonly fw: AIFirewall,
      private readonly threshold = 5,
      private readonly resetTimeout = 30000
    ) {}

    async execute(
      agent: string,
      action: string,
      params: Record<string, unknown>
    ) {
      // Check if circuit is open
      if (this.state === "open") {
        if (Date.now() - this.lastFailure > this.resetTimeout) {
          this.state = "half-open";
          console.log("   Circuit: half-open (testing)");
        } else {
          console.log("   Circuit: open (fast fail)");
          throw new Error("Circuit breaker is open");
        }
      }

      try {
        const result = await this.fw.execute(agent, action, params);

        // Success - reset circuit
        if (this.state === "half-open") {
          this.state = "closed";
          this.failures = 0;
          console.log("   Circuit: closed (recovered)");
        }

        return result;
      } catch (error) {
        if (error instanceof NetworkError) {
          this.failures++;
          this.lastFailure = Date.now();

          if (this.failures >= this.threshold) {
            this.state = "open";
            console.log(`   Circuit: open (${this.failures} failures)`);
          }
        }

        throw error;
      }
    }
  }

  const circuitBreaker = new CircuitBreaker(fwNoRetry, 3, 10000);
  console.log("   Circuit breaker configured: 3 failures = open, 10s reset\n");

  // =========================================
  // 5. Graceful Degradation
  // =========================================
  console.log("5️⃣  Graceful Degradation Pattern\n");

  async function executeWithFallback(
    agent: string,
    action: string,
    params: Record<string, unknown>,
    fallbackBehavior: "allow" | "block" | "cache"
  ) {
    try {
      return await fwDefault.execute(agent, action, params);
    } catch (error) {
      if (error instanceof NetworkError) {
        console.log(`   ⚠️  Network error - using fallback: ${fallbackBehavior}`);

        switch (fallbackBehavior) {
          case "allow":
            // Fail open (dangerous for security)
            return {
              allowed: true,
              actionId: null,
              timestamp: new Date(),
              simulated: false,
              reason: "Fallback: allowed due to service unavailability",
            };

          case "block":
            // Fail closed (recommended for security)
            return {
              allowed: false,
              actionId: null,
              timestamp: new Date(),
              simulated: false,
              reason: "Service unavailable - action blocked for safety",
            };

          case "cache":
            // Use cached policy decision (would need cache implementation)
            console.log("   Would check cache for previous decision");
            return {
              allowed: false,
              actionId: null,
              timestamp: new Date(),
              simulated: false,
              reason: "No cached decision available",
            };
        }
      }

      throw error;
    }
  }

  console.log("   Example: executeWithFallback(agent, action, params, 'block')\n");

  // =========================================
  // 6. Logging and Monitoring
  // =========================================
  console.log("6️⃣  Logging and Monitoring\n");

  class MonitoredFirewall {
    private metrics = {
      requests: 0,
      successes: 0,
      failures: 0,
      blocked: 0,
      totalLatency: 0,
      errors: new Map<string, number>(),
    };

    constructor(private fw: AIFirewall) {}

    async execute(
      agent: string,
      action: string,
      params: Record<string, unknown>
    ) {
      const start = Date.now();
      this.metrics.requests++;

      try {
        const result = await this.fw.execute(agent, action, params);
        this.metrics.successes++;
        this.metrics.totalLatency += Date.now() - start;

        if (!result.allowed) {
          this.metrics.blocked++;
        }

        return result;
      } catch (error) {
        this.metrics.failures++;
        this.metrics.totalLatency += Date.now() - start;

        const errorType = error instanceof Error ? error.constructor.name : "Unknown";
        this.metrics.errors.set(
          errorType,
          (this.metrics.errors.get(errorType) || 0) + 1
        );

        throw error;
      }
    }

    getMetrics() {
      return {
        ...this.metrics,
        avgLatency:
          this.metrics.requests > 0
            ? this.metrics.totalLatency / this.metrics.requests
            : 0,
        successRate:
          this.metrics.requests > 0
            ? (this.metrics.successes / this.metrics.requests) * 100
            : 0,
        errorsByType: Object.fromEntries(this.metrics.errors),
      };
    }
  }

  const monitored = new MonitoredFirewall(fwDefault);

  // Make some requests
  await monitored.execute("agent", "allowed_action", {});
  try {
    await monitored.execute("agent", "blocked_action", {});
  } catch {}

  console.log("   Metrics:", monitored.getMetrics());

  console.log("\n✨ Example complete!");
}

main().catch(console.error);
