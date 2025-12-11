/**
 * Strict Mode Example
 *
 * This example demonstrates using strict mode, where blocked actions
 * throw ActionBlockedError instead of returning a result.
 *
 * Strict mode is useful when you want to use try/catch for control flow
 * and ensure blocked actions are always handled.
 *
 * To run:
 *   1. Start the AI Agent Filter server: docker-compose up -d
 *   2. Set environment variables: export AI_FIREWALL_API_KEY=af_xxx
 *   3. Run: npx tsx examples/strict-mode.ts
 */

import { AIFirewall, ActionBlockedError, AIFirewallError } from "../src/index.js";

async function main() {
  // Initialize client with strict mode enabled
  const fw = new AIFirewall({
    apiKey: process.env.AI_FIREWALL_API_KEY || "af_test_key",
    projectId: "strict-mode-example",
    baseUrl: process.env.AI_FIREWALL_URL || "http://localhost:8000",
    strict: true, // Enable strict mode
  });

  console.log("🔥 AI Agent Filter - Strict Mode Example\n");

  // Set up a restrictive policy
  await fw.updatePolicy({
    name: "strict-policy",
    version: "1.0",
    default: "block",
    rules: [
      {
        action_type: "safe_action",
        effect: "allow",
      },
      {
        action_type: "limited_action",
        effect: "allow",
        constraints: {
          "params.value": { max: 100 },
        },
      },
    ],
  });

  console.log("📋 Policy configured\n");

  // =========================================
  // Example 1: Allowed action (no exception)
  // =========================================
  console.log("1️⃣  Testing allowed action...");
  try {
    const result = await fw.execute("agent", "safe_action", { data: "hello" });
    console.log(`   ✅ Action allowed! ID: ${result.actionId}\n`);
  } catch (error) {
    console.log(`   ❌ Unexpected error: ${error}\n`);
  }

  // =========================================
  // Example 2: Blocked action (throws exception)
  // =========================================
  console.log("2️⃣  Testing blocked action...");
  try {
    await fw.execute("agent", "dangerous_action", { destroy: true });
    console.log("   ✅ This should not print!\n");
  } catch (error) {
    if (error instanceof ActionBlockedError) {
      console.log(`   ❌ Action blocked!`);
      console.log(`      Reason: ${error.reason}`);
      console.log(`      Action ID: ${error.actionId}\n`);
    } else {
      throw error;
    }
  }

  // =========================================
  // Example 3: Constraint violation
  // =========================================
  console.log("3️⃣  Testing constraint violation...");
  try {
    await fw.execute("agent", "limited_action", { value: 500 }); // Exceeds max: 100
    console.log("   ✅ This should not print!\n");
  } catch (error) {
    if (error instanceof ActionBlockedError) {
      console.log(`   ❌ Constraint violated!`);
      console.log(`      Reason: ${error.reason}`);
      console.log(`      Action ID: ${error.actionId}\n`);
    } else {
      throw error;
    }
  }

  // =========================================
  // Example 4: Simulations don't throw
  // =========================================
  console.log("4️⃣  Testing simulation (no throw even when blocked)...");
  try {
    const simResult = await fw.execute(
      "agent",
      "dangerous_action",
      { destroy: true },
      { simulate: true }
    );
    console.log(`   📋 Simulation result: ${simResult.allowed ? "Would allow" : "Would block"}`);
    console.log(`      Reason: ${simResult.reason || "N/A"}`);
    console.log(`      Simulated: ${simResult.simulated}\n`);
  } catch (error) {
    console.log(`   ❌ Unexpected error in simulation: ${error}\n`);
  }

  // =========================================
  // Example 5: Real-world pattern
  // =========================================
  console.log("5️⃣  Real-world usage pattern...\n");

  async function processUserRequest(action: string, params: Record<string, unknown>) {
    try {
      // This will throw if blocked
      await fw.execute("user-request-handler", action, params);

      // If we get here, action is allowed
      console.log(`   Processing ${action}...`);
      await performAction(action, params);
      console.log(`   ✅ ${action} completed successfully\n`);

      return { success: true };
    } catch (error) {
      if (error instanceof ActionBlockedError) {
        console.log(`   ❌ Request denied: ${error.reason}`);
        console.log(`   📝 Logged with ID: ${error.actionId}\n`);
        return { success: false, error: error.reason };
      }

      // Re-throw unexpected errors
      throw error;
    }
  }

  // Test with allowed action
  await processUserRequest("safe_action", { user: "john" });

  // Test with blocked action
  await processUserRequest("delete_account", { userId: "12345" });

  console.log("✨ Example complete!");
}

async function performAction(action: string, params: Record<string, unknown>) {
  // Simulate actual action execution
  await new Promise((resolve) => setTimeout(resolve, 100));
}

main().catch(console.error);
