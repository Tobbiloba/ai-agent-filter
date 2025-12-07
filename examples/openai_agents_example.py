"""
OpenAI Agents Integration Example with AI Firewall

This example shows how to integrate AI Firewall with OpenAI's function calling
and the Agents API to validate tool executions before they run.

Prerequisites:
    pip install openai ai-firewall

Usage:
    1. Start the AI Firewall server
    2. Create a project and configure policies
    3. Set OPENAI_API_KEY environment variable
    4. Run this script
"""

import json
from typing import Any

# Note: Uncomment when you have openai installed
# import openai

from ai_firewall import AIFirewall, ActionBlockedError


# ============================================================================
# Firewall-Protected Tool Executor
# ============================================================================

class ProtectedToolExecutor:
    """
    Executes OpenAI function calls with AI Firewall validation.

    This class wraps your tool functions and validates each call
    through the firewall before execution.
    """

    def __init__(self, firewall: AIFirewall, agent_name: str = "openai_agent"):
        self.firewall = firewall
        self.agent_name = agent_name
        self.tools = {}

    def register_tool(self, name: str, func: callable, description: str = ""):
        """Register a tool function."""
        self.tools[name] = {
            "function": func,
            "description": description,
        }

    def execute(self, tool_name: str, arguments: dict) -> dict:
        """
        Execute a tool with firewall validation.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments for the tool

        Returns:
            Tool result or error dict
        """
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        # Validate with firewall
        result = self.firewall.execute(
            agent_name=self.agent_name,
            action_type=tool_name,
            params=arguments,
        )

        if not result.allowed:
            return {
                "error": "Action blocked by policy",
                "reason": result.reason,
                "action_id": result.action_id,
            }

        # Execute the actual tool
        try:
            tool_result = self.tools[tool_name]["function"](**arguments)
            return {
                "success": True,
                "result": tool_result,
                "action_id": result.action_id,
            }
        except Exception as e:
            return {"error": str(e), "action_id": result.action_id}


# ============================================================================
# Example Tools (simulated)
# ============================================================================

def search_database(query: str, limit: int = 10) -> list:
    """Search the database for records."""
    print(f"   🔍 Searching database: '{query}' (limit: {limit})")
    return [
        {"id": 1, "name": "Result 1", "match": 0.95},
        {"id": 2, "name": "Result 2", "match": 0.87},
    ]


def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email."""
    print(f"   📧 Sending email to: {to}")
    print(f"      Subject: {subject}")
    return {"sent": True, "to": to}


def execute_sql(query: str) -> list:
    """Execute a SQL query (dangerous - should be heavily restricted!)."""
    print(f"   ⚠️  Executing SQL: {query}")
    return [{"warning": "This is a simulated result"}]


def transfer_funds(from_account: str, to_account: str, amount: float) -> dict:
    """Transfer funds between accounts."""
    print(f"   💰 Transferring ${amount} from {from_account} to {to_account}")
    return {"transferred": amount, "from": from_account, "to": to_account}


# ============================================================================
# OpenAI Function Definitions (for reference)
# ============================================================================

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "Search the database for records matching a query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a recipient",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_funds",
            "description": "Transfer funds between accounts",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_account": {"type": "string"},
                    "to_account": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["from_account", "to_account", "amount"],
            },
        },
    },
]


# ============================================================================
# Main Demo
# ============================================================================

def main():
    """Demo of AI Firewall with OpenAI-style function calling."""

    print("\n" + "=" * 60)
    print("AI Firewall + OpenAI Function Calling Demo")
    print("=" * 60)

    # Initialize firewall
    fw = AIFirewall(
        api_key="af_your_api_key_here",
        project_id="openai-agent-prod",
        base_url="http://localhost:8000",
    )

    # Create protected executor
    executor = ProtectedToolExecutor(fw, agent_name="gpt4_assistant")

    # Register tools
    executor.register_tool("search_database", search_database)
    executor.register_tool("send_email", send_email)
    executor.register_tool("execute_sql", execute_sql)
    executor.register_tool("transfer_funds", transfer_funds)

    # Simulate function calls that would come from OpenAI
    test_calls = [
        {
            "name": "search_database",
            "arguments": {"query": "customer orders", "limit": 5},
            "description": "Safe search operation",
        },
        {
            "name": "send_email",
            "arguments": {
                "to": "user@company.com",
                "subject": "Report Ready",
                "body": "Your report is ready.",
            },
            "description": "Internal email (should be allowed)",
        },
        {
            "name": "send_email",
            "arguments": {
                "to": "external@gmail.com",
                "subject": "Data Export",
                "body": "Sensitive data attached.",
            },
            "description": "External email (might be blocked by policy)",
        },
        {
            "name": "transfer_funds",
            "arguments": {
                "from_account": "checking",
                "to_account": "savings",
                "amount": 500,
            },
            "description": "Small transfer (should be allowed)",
        },
        {
            "name": "transfer_funds",
            "arguments": {
                "from_account": "checking",
                "to_account": "external",
                "amount": 50000,
            },
            "description": "Large external transfer (should be blocked)",
        },
        {
            "name": "execute_sql",
            "arguments": {"query": "DROP TABLE users;"},
            "description": "Dangerous SQL (should definitely be blocked!)",
        },
    ]

    # Execute each simulated function call
    for call in test_calls:
        print(f"\n{'─' * 60}")
        print(f"Tool: {call['name']}")
        print(f"Description: {call['description']}")
        print(f"Arguments: {json.dumps(call['arguments'], indent=2)}")
        print("─" * 60)

        result = executor.execute(call["name"], call["arguments"])

        if "error" in result:
            print(f"❌ BLOCKED: {result.get('reason', result.get('error'))}")
        else:
            print(f"✅ ALLOWED: {result.get('result')}")

        if "action_id" in result:
            print(f"   Action ID: {result['action_id']}")

    fw.close()


# ============================================================================
# Full OpenAI Integration (when openai is installed)
# ============================================================================

"""
# Uncomment this section for full OpenAI integration

import openai

def run_openai_agent_with_firewall():
    '''
    Run an OpenAI agent with firewall-protected tool execution.
    '''
    # Initialize clients
    openai_client = openai.OpenAI()
    fw = AIFirewall(api_key="...", project_id="...")
    executor = ProtectedToolExecutor(fw)

    # Register your tools
    executor.register_tool("search_database", search_database)
    executor.register_tool("send_email", send_email)
    executor.register_tool("transfer_funds", transfer_funds)

    messages = [
        {"role": "user", "content": "Search for recent orders and email the results to admin@company.com"}
    ]

    # Initial completion with tools
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=OPENAI_TOOLS,
    )

    # Process tool calls
    while response.choices[0].message.tool_calls:
        tool_calls = response.choices[0].message.tool_calls
        messages.append(response.choices[0].message)

        for tool_call in tool_calls:
            # Parse the function call
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            # Execute with firewall protection
            result = executor.execute(func_name, func_args)

            # Add result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

        # Continue the conversation
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=OPENAI_TOOLS,
        )

    print("Final response:", response.choices[0].message.content)
    fw.close()
"""


if __name__ == "__main__":
    print("AI Firewall + OpenAI Agents Integration")
    print("=" * 60)
    print("Note: Update API credentials before running")
    print("=" * 60)

    # Uncomment to run (requires server + valid credentials)
    # main()

    print("\nThis example demonstrates:")
    print("1. ProtectedToolExecutor - validates all function calls")
    print("2. Tool registration and execution")
    print("3. Handling blocked vs allowed actions")
    print("4. Integration with OpenAI function calling format")
