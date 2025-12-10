/**
 * Integration test for Node.js SDK against live server.
 * Run with: npx tsx tests/integration.test.ts
 */

import { AIFirewall, ActionBlockedError, PolicyNotFoundError } from "../src/index.js";

const BASE_URL = "http://127.0.0.1:8000";

async function runTests() {
  console.log("========================================");
  console.log("Node.js SDK Integration Tests");
  console.log("========================================\n");

  let passed = 0;
  let failed = 0;

  // 1. Create a project first (need API key)
  console.log("1. Creating test project...");
  const projectId = `nodejs-test-${Math.floor(Math.random() * 100000)}`;
  const projectRes = await fetch(`${BASE_URL}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: projectId, name: "Node.js SDK Test" }),
  });
  const project = await projectRes.json() as { api_key: string };
  const apiKey = project.api_key;
  console.log(`   Project created: ${projectId}`);
  console.log(`   API Key: ${apiKey.substring(0, 20)}...\n`);

  const fw = new AIFirewall({
    apiKey,
    projectId,
    baseUrl: BASE_URL,
  });

  // Test 2: getPolicy (should fail - no policy yet)
  console.log("2. Testing getPolicy (no policy)...");
  try {
    await fw.getPolicy();
    console.log("   FAILED: Should have thrown PolicyNotFoundError\n");
    failed++;
  } catch (error) {
    if (error instanceof PolicyNotFoundError) {
      console.log("   PASSED: PolicyNotFoundError thrown\n");
      passed++;
    } else {
      console.log(`   FAILED: Wrong error type: ${error}\n`);
      failed++;
    }
  }

  // Test 3: updatePolicy
  console.log("3. Testing updatePolicy...");
  try {
    const policy = await fw.updatePolicy({
      name: "test-policy",
      version: "1.0",
      rules: [
        {
          action_type: "pay_invoice",
          constraints: {
            "params.amount": { max: 10000 },
          },
        },
      ],
      default: "allow",
    });
    if (policy.name === "test-policy" && policy.version === "1.0") {
      console.log(`   PASSED: Policy created - ${policy.name} v${policy.version}\n`);
      passed++;
    } else {
      console.log(`   FAILED: Wrong policy data\n`);
      failed++;
    }
  } catch (error) {
    console.log(`   FAILED: ${error}\n`);
    failed++;
  }

  // Test 4: getPolicy (should succeed now)
  console.log("4. Testing getPolicy (with policy)...");
  try {
    const policy = await fw.getPolicy();
    if (policy.name === "test-policy" && policy.isActive) {
      console.log(`   PASSED: Got policy - ${policy.name}, active: ${policy.isActive}\n`);
      passed++;
    } else {
      console.log(`   FAILED: Wrong policy data\n`);
      failed++;
    }
  } catch (error) {
    console.log(`   FAILED: ${error}\n`);
    failed++;
  }

  // Test 5: execute (allowed action)
  console.log("5. Testing execute (allowed action)...");
  try {
    const result = await fw.execute("test-agent", "test-action", { key: "value" });
    if (result.allowed && result.actionId && result.timestamp) {
      console.log(`   PASSED: Action allowed - ${result.actionId}\n`);
      passed++;
    } else {
      console.log(`   FAILED: Expected allowed action\n`);
      failed++;
    }
  } catch (error) {
    console.log(`   FAILED: ${error}\n`);
    failed++;
  }

  // Test 6: execute (action with constraints - should allow within limit)
  console.log("6. Testing execute (within constraint)...");
  try {
    const result = await fw.execute("test-agent", "pay_invoice", { amount: 5000 });
    if (result.allowed) {
      console.log(`   PASSED: Action allowed (amount 5000 < 10000)\n`);
      passed++;
    } else {
      console.log(`   FAILED: Should have been allowed: ${result.reason}\n`);
      failed++;
    }
  } catch (error) {
    console.log(`   FAILED: ${error}\n`);
    failed++;
  }

  // Test 7: execute (action exceeding constraint - should block)
  console.log("7. Testing execute (exceeds constraint)...");
  try {
    const result = await fw.execute("test-agent", "pay_invoice", { amount: 15000 });
    if (!result.allowed && result.reason) {
      console.log(`   PASSED: Action blocked - ${result.reason}\n`);
      passed++;
    } else {
      console.log(`   FAILED: Should have been blocked\n`);
      failed++;
    }
  } catch (error) {
    console.log(`   FAILED: ${error}\n`);
    failed++;
  }

  // Test 8: strict mode
  console.log("8. Testing strict mode...");
  const fwStrict = new AIFirewall({
    apiKey,
    projectId,
    baseUrl: BASE_URL,
    strict: true,
  });
  try {
    await fwStrict.execute("test-agent", "pay_invoice", { amount: 20000 });
    console.log("   FAILED: Should have thrown ActionBlockedError\n");
    failed++;
  } catch (error) {
    if (error instanceof ActionBlockedError) {
      console.log(`   PASSED: ActionBlockedError thrown - ${error.reason}\n`);
      passed++;
    } else {
      console.log(`   FAILED: Wrong error type: ${error}\n`);
      failed++;
    }
  }

  // Test 9: getLogs
  console.log("9. Testing getLogs...");
  try {
    const logs = await fw.getLogs({ page: 1, pageSize: 10 });
    if (Array.isArray(logs.items) && typeof logs.total === "number") {
      console.log(`   PASSED: Got ${logs.items.length} logs (total: ${logs.total})\n`);
      passed++;
    } else {
      console.log(`   FAILED: Invalid logs structure\n`);
      failed++;
    }
  } catch (error) {
    console.log(`   FAILED: ${error}\n`);
    failed++;
  }

  // Test 10: getStats
  console.log("10. Testing getStats...");
  try {
    const stats = await fw.getStats();
    if (typeof stats.totalActions === "number" && typeof stats.blockRate === "number") {
      console.log(`   PASSED: Total actions: ${stats.totalActions}, Block rate: ${stats.blockRate}%\n`);
      passed++;
    } else {
      console.log(`   FAILED: Invalid stats structure\n`);
      failed++;
    }
  } catch (error) {
    console.log(`   FAILED: ${error}\n`);
    failed++;
  }

  // Summary
  console.log("========================================");
  console.log(`Results: ${passed} passed, ${failed} failed`);
  console.log("========================================");

  fw.close();
  fwStrict.close();

  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch((err) => {
  console.error("Test runner error:", err);
  process.exit(1);
});
