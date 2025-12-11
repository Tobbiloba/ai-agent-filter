/**
 * Basic Usage Example
 *
 * This example demonstrates the core functionality of the AI Agent Filter SDK.
 *
 * To run:
 *   1. Start the AI Agent Filter server: docker-compose up -d
 *   2. Set environment variables: export AI_FIREWALL_API_KEY=af_xxx
 *   3. Run: npx tsx examples/basic-usage.ts
 */

import { AIFirewall, ActionBlockedError } from "../src/index.js";

async function main() {
  // Initialize the client
  const fw = new AIFirewall({
    apiKey: process.env.AI_FIREWALL_API_KEY || "af_test_key",
    projectId: "example-project",
    baseUrl: process.env.AI_FIREWALL_URL || "http://localhost:8000",
  });

  console.log("🔥 AI Agent Filter - Basic Usage Example\n");

  // =========================================
  // 1. Set up a policy
  // =========================================
  console.log("📋 Setting up policy...");

  const policy = await fw.updatePolicy({
    name: "example-policy",
    version: "1.0",
    default: "block", // Block everything by default
    rules: [
      {
        // Allow sending emails, but only to company domain
        action_type: "send_email",
        effect: "allow",
        constraints: {
          "params.to": { pattern: "^[\\w.-]+@company\\.com$" },
        },
        rate_limit: {
          max_requests: 10,
          window_seconds: 60,
        },
      },
      {
        // Allow payments up to $1000
        action_type: "process_payment",
        effect: "allow",
        constraints: {
          "params.amount": { min: 1, max: 1000 },
          "params.currency": { in: ["USD", "EUR"] },
        },
      },
      {
        // Allow read operations without restrictions
        action_type: "read_data",
        effect: "allow",
      },
    ],
  });

  console.log(`✅ Policy created: ${policy.name} v${policy.version}\n`);

  // =========================================
  // 2. Validate allowed actions
  // =========================================
  console.log("🔍 Testing allowed actions...\n");

  // Allowed: Email to company domain
  const emailResult = await fw.execute("support-bot", "send_email", {
    to: "user@company.com",
    subject: "Hello",
    body: "This is a test email",
  });
  console.log(`  send_email (company): ${emailResult.allowed ? "✅ Allowed" : "❌ Blocked"}`);

  // Allowed: Payment under limit
  const paymentResult = await fw.execute("payment-agent", "process_payment", {
    amount: 500,
    currency: "USD",
    recipient: "vendor@example.com",
  });
  console.log(`  process_payment ($500): ${paymentResult.allowed ? "✅ Allowed" : "❌ Blocked"}`);

  // Allowed: Read operation
  const readResult = await fw.execute("data-agent", "read_data", {
    table: "users",
    limit: 100,
  });
  console.log(`  read_data: ${readResult.allowed ? "✅ Allowed" : "❌ Blocked"}`);

  // =========================================
  // 3. Validate blocked actions
  // =========================================
  console.log("\n🚫 Testing blocked actions...\n");

  // Blocked: Email to external domain
  const externalEmail = await fw.execute("support-bot", "send_email", {
    to: "user@external.com",
    subject: "Hello",
  });
  console.log(`  send_email (external): ${externalEmail.allowed ? "✅ Allowed" : `❌ Blocked - ${externalEmail.reason}`}`);

  // Blocked: Payment over limit
  const largePayment = await fw.execute("payment-agent", "process_payment", {
    amount: 5000,
    currency: "USD",
  });
  console.log(`  process_payment ($5000): ${largePayment.allowed ? "✅ Allowed" : `❌ Blocked - ${largePayment.reason}`}`);

  // Blocked: Undefined action (default: block)
  const deleteResult = await fw.execute("admin-agent", "delete_all_data", {
    confirm: true,
  });
  console.log(`  delete_all_data: ${deleteResult.allowed ? "✅ Allowed" : `❌ Blocked - ${deleteResult.reason}`}`);

  // =========================================
  // 4. Simulation mode (what-if testing)
  // =========================================
  console.log("\n🧪 Testing simulation mode...\n");

  const simResult = await fw.execute(
    "test-agent",
    "dangerous_action",
    { destructive: true },
    { simulate: true }
  );

  console.log(`  Simulation result: ${simResult.allowed ? "Would be allowed" : `Would be blocked - ${simResult.reason}`}`);
  console.log(`  Action ID: ${simResult.actionId || "null (simulation)"}`);
  console.log(`  Simulated: ${simResult.simulated}`);

  // =========================================
  // 5. Get statistics
  // =========================================
  console.log("\n📊 Validation statistics...\n");

  const stats = await fw.getStats();
  console.log(`  Total actions: ${stats.totalActions}`);
  console.log(`  Allowed: ${stats.allowed}`);
  console.log(`  Blocked: ${stats.blocked}`);
  console.log(`  Block rate: ${stats.blockRate.toFixed(1)}%`);

  // =========================================
  // 6. Get recent audit logs
  // =========================================
  console.log("\n📜 Recent audit logs...\n");

  const logs = await fw.getLogs({ pageSize: 5 });
  for (const log of logs.items) {
    const status = log.allowed ? "✅" : "❌";
    console.log(`  ${status} [${log.agentName}] ${log.actionType} - ${log.reason || "OK"}`);
  }

  console.log("\n✨ Example complete!");
}

main().catch(console.error);
