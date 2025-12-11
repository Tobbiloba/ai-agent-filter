/**
 * LangChain.js Integration Example
 *
 * This example demonstrates how to integrate AI Agent Filter
 * with LangChain.js agents and tools.
 *
 * To run:
 *   1. npm install @langchain/core @langchain/openai
 *   2. Start the AI Agent Filter server: docker-compose up -d
 *   3. Set environment variables
 *   4. Run: npx tsx examples/langchain-integration.ts
 */

import { AIFirewall, ActionBlockedError } from "../src/index.js";

// Note: These would be actual LangChain imports in a real project
// import { DynamicTool, Tool } from "@langchain/core/tools";
// import { ChatOpenAI } from "@langchain/openai";
// import { AgentExecutor, createOpenAIFunctionsAgent } from "langchain/agents";

// Initialize the AI Firewall client
const fw = new AIFirewall({
  apiKey: process.env.AI_FIREWALL_API_KEY || "af_test_key",
  projectId: "langchain-agent",
  baseUrl: process.env.AI_FIREWALL_URL || "http://localhost:8000",
});

/**
 * Higher-order function to wrap any tool with AI Agent Filter validation
 */
function withFirewall<T extends { name: string; _call: (input: string) => Promise<string> }>(
  tool: T,
  agentName: string,
  parseInput?: (input: string) => Record<string, unknown>
): T {
  const originalCall = tool._call.bind(tool);

  tool._call = async (input: string): Promise<string> => {
    // Parse the input into params for validation
    const params = parseInput ? parseInput(input) : { input };

    // Validate the tool call
    const result = await fw.execute(agentName, tool.name, params);

    if (!result.allowed) {
      // Return a message to the LLM explaining why the action was blocked
      return `Action blocked by security policy: ${result.reason}. Please try a different approach.`;
    }

    // Execute the actual tool
    return originalCall(input);
  };

  return tool;
}

/**
 * Create a validated tool from scratch
 */
function createValidatedTool(config: {
  name: string;
  description: string;
  agentName: string;
  execute: (input: string) => Promise<string>;
  parseInput?: (input: string) => Record<string, unknown>;
}) {
  const { name, description, agentName, execute, parseInput } = config;

  return {
    name,
    description,
    async _call(input: string): Promise<string> {
      const params = parseInput ? parseInput(input) : { input };

      const result = await fw.execute(agentName, name, params);

      if (!result.allowed) {
        return `Action blocked: ${result.reason}`;
      }

      return execute(input);
    },
  };
}

// =========================================
// Example Tools
// =========================================

// Simulated calculator tool
const calculatorTool = {
  name: "calculator",
  description: "Useful for math calculations",
  async _call(input: string): Promise<string> {
    // In reality, this would evaluate the math expression
    return `Result: ${eval(input)}`; // Note: Don't use eval in production!
  },
};

// Simulated email tool
const emailTool = {
  name: "send_email",
  description: "Send an email to a recipient",
  async _call(input: string): Promise<string> {
    const { to, subject, body } = JSON.parse(input);
    // In reality, this would send an email
    return `Email sent to ${to}`;
  },
};

// Simulated payment tool
const paymentTool = {
  name: "process_payment",
  description: "Process a payment transaction",
  async _call(input: string): Promise<string> {
    const { amount, currency, recipient } = JSON.parse(input);
    // In reality, this would process a payment
    return `Payment of ${amount} ${currency} sent to ${recipient}`;
  },
};

// Simulated file delete tool
const deleteFileTool = {
  name: "delete_file",
  description: "Delete a file from the system",
  async _call(input: string): Promise<string> {
    const { path } = JSON.parse(input);
    // In reality, this would delete a file
    return `File deleted: ${path}`;
  },
};

// =========================================
// Main Example
// =========================================

async function main() {
  console.log("🔥 AI Agent Filter - LangChain.js Integration Example\n");

  // Set up the policy
  await fw.updatePolicy({
    name: "langchain-policy",
    version: "1.0",
    default: "block",
    rules: [
      {
        // Allow calculator with no restrictions
        action_type: "calculator",
        effect: "allow",
      },
      {
        // Allow emails only to company domain
        action_type: "send_email",
        effect: "allow",
        constraints: {
          "params.to": { pattern: "^[\\w.-]+@company\\.com$" },
        },
      },
      {
        // Allow payments up to $1000
        action_type: "process_payment",
        effect: "allow",
        constraints: {
          "params.amount": { max: 1000 },
          "params.currency": { in: ["USD", "EUR"] },
        },
      },
      // Note: delete_file is NOT in the policy, so it will be blocked
    ],
  });

  console.log("📋 Policy configured\n");

  // Wrap tools with firewall validation
  const validatedCalculator = withFirewall(calculatorTool, "math-agent");

  const validatedEmail = withFirewall(emailTool, "email-agent", (input) => {
    try {
      return JSON.parse(input);
    } catch {
      return { input };
    }
  });

  const validatedPayment = withFirewall(paymentTool, "payment-agent", (input) => {
    try {
      return JSON.parse(input);
    } catch {
      return { input };
    }
  });

  const validatedDelete = withFirewall(deleteFileTool, "file-agent", (input) => {
    try {
      return JSON.parse(input);
    } catch {
      return { input };
    }
  });

  // Test the tools
  console.log("🧪 Testing validated tools...\n");

  // 1. Calculator (allowed)
  console.log("1️⃣  Calculator: 2 + 2");
  const calcResult = await validatedCalculator._call("2 + 2");
  console.log(`   Result: ${calcResult}\n`);

  // 2. Email to company domain (allowed)
  console.log("2️⃣  Email to company domain");
  const companyEmail = await validatedEmail._call(
    JSON.stringify({
      to: "alice@company.com",
      subject: "Hello",
      body: "Test message",
    })
  );
  console.log(`   Result: ${companyEmail}\n`);

  // 3. Email to external domain (blocked)
  console.log("3️⃣  Email to external domain");
  const externalEmail = await validatedEmail._call(
    JSON.stringify({
      to: "bob@external.com",
      subject: "Hello",
      body: "Test message",
    })
  );
  console.log(`   Result: ${externalEmail}\n`);

  // 4. Small payment (allowed)
  console.log("4️⃣  Payment: $500 USD");
  const smallPayment = await validatedPayment._call(
    JSON.stringify({
      amount: 500,
      currency: "USD",
      recipient: "vendor@example.com",
    })
  );
  console.log(`   Result: ${smallPayment}\n`);

  // 5. Large payment (blocked)
  console.log("5️⃣  Payment: $5000 USD");
  const largePayment = await validatedPayment._call(
    JSON.stringify({
      amount: 5000,
      currency: "USD",
      recipient: "vendor@example.com",
    })
  );
  console.log(`   Result: ${largePayment}\n`);

  // 6. Delete file (blocked - not in policy)
  console.log("6️⃣  Delete file");
  const deleteResult = await validatedDelete._call(
    JSON.stringify({
      path: "/important/data.txt",
    })
  );
  console.log(`   Result: ${deleteResult}\n`);

  // =========================================
  // Example: Creating a Validated Agent
  // =========================================
  console.log("📝 Example agent setup code:\n");
  console.log(`
// In a real LangChain.js application:

import { DynamicTool } from "@langchain/core/tools";
import { ChatOpenAI } from "@langchain/openai";
import { AgentExecutor, createOpenAIFunctionsAgent } from "langchain/agents";

// Create validated tools
const tools = [
  new DynamicTool({
    name: "send_email",
    description: "Send an email",
    func: async (input) => {
      const params = JSON.parse(input);
      const result = await fw.execute("email-agent", "send_email", params);
      if (!result.allowed) {
        return \`Cannot send email: \${result.reason}\`;
      }
      return await sendEmail(params);
    },
  }),
];

// Create agent with validated tools
const model = new ChatOpenAI({ modelName: "gpt-4" });
const agent = await createOpenAIFunctionsAgent({ llm: model, tools, prompt });
const executor = new AgentExecutor({ agent, tools });

// Run the agent
const result = await executor.invoke({
  input: "Send an email to user@company.com",
});
  `);

  // Show statistics
  console.log("\n📊 Validation Statistics:");
  const stats = await fw.getStats();
  console.log(`   Total tool calls: ${stats.totalActions}`);
  console.log(`   Allowed: ${stats.allowed}`);
  console.log(`   Blocked: ${stats.blocked}`);
  console.log(`   Block rate: ${stats.blockRate.toFixed(1)}%`);

  console.log("\n✨ Example complete!");
}

main().catch(console.error);
