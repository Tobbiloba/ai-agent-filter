"""
LangChain + AI Firewall Demo

This demo shows all three integration patterns without requiring
an actual LLM API key. It uses mocked responses to demonstrate
how the firewall protects LangChain tool executions.

Run this demo:
    1. Start the AI Firewall server: uvicorn server.app:app --reload
    2. Create a project and get your API key
    3. Update the credentials below
    4. Run: python demo.py

Or run in mock mode (no server needed):
    python demo.py --mock
"""

import sys
from typing import Any, Dict

# Check for mock mode
MOCK_MODE = "--mock" in sys.argv


# ============================================================================
# Mock Firewall for Demo (when server isn't running)
# ============================================================================

class MockValidationResult:
    """Mock validation result for demo purposes."""

    def __init__(self, allowed: bool, reason: str = None):
        self.allowed = allowed
        self.action_id = "act_mock123"
        self.reason = reason
        self.execution_time_ms = 1


class MockFirewall:
    """
    Mock AI Firewall client for demo purposes.

    This simulates firewall behavior without needing a running server.
    In production, use the real AIFirewall client.
    """

    def __init__(self, **kwargs):
        # Simple policy: block payments over $10,000
        self.max_payment = 10000
        self.blocked_domains = ["spam.com", "evil.org"]

    def execute(
        self,
        agent_name: str,
        action_type: str,
        params: Dict[str, Any] = None,
    ) -> MockValidationResult:
        """Simulate firewall validation."""
        params = params or {}

        # Simulate policy checks
        if action_type == "pay_invoice":
            amount = params.get("amount", 0)
            if amount > self.max_payment:
                return MockValidationResult(
                    allowed=False,
                    reason=f"Amount ${amount} exceeds maximum ${self.max_payment}"
                )

        if action_type == "send_email":
            to = params.get("to", "")
            for domain in self.blocked_domains:
                if domain in to:
                    return MockValidationResult(
                        allowed=False,
                        reason=f"Email to {domain} is blocked"
                    )

        if action_type == "execute_sql":
            return MockValidationResult(
                allowed=False,
                reason="SQL execution is blocked for all agents"
            )

        return MockValidationResult(allowed=True)

    def close(self):
        pass


# ============================================================================
# Get Firewall Client
# ============================================================================

def get_firewall():
    """Get firewall client (real or mock based on mode)."""
    if MOCK_MODE:
        print("🔸 Running in MOCK mode (no server needed)")
        print()
        return MockFirewall()
    else:
        try:
            from ai_firewall import AIFirewall
            return AIFirewall(
                api_key="YOUR_API_KEY_HERE",  # Replace with your key
                project_id="langchain-demo",   # Replace with your project
                base_url="http://localhost:8000",
            )
        except Exception as e:
            print(f"❌ Could not connect to AI Firewall: {e}")
            print("   Run with --mock flag to demo without server")
            sys.exit(1)


# ============================================================================
# Demo 1: Tool Wrapper Pattern
# ============================================================================

def demo_tool_wrapper():
    """Demonstrate the @protected_tool decorator pattern."""
    print("=" * 60)
    print("Demo 1: Tool Wrapper Pattern")
    print("=" * 60)
    print()

    fw = get_firewall()

    # Import our wrapper
    from tool_wrapper import protected_tool

    @protected_tool(fw, "invoice_agent")
    def pay_invoice(vendor: str, amount: float, currency: str = "USD") -> str:
        """Pay an invoice to a vendor."""
        return f"✅ Paid ${amount} {currency} to {vendor}"

    @protected_tool(fw, "email_agent")
    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email to a recipient."""
        return f"✅ Email sent to {to}: {subject}"

    # Test allowed actions
    print("Testing allowed actions:")
    print(f"  pay_invoice($5,000): {pay_invoice(vendor='Acme Corp', amount=5000)}")
    print(f"  send_email(user@company.com): {send_email(to='user@company.com', subject='Hello', body='Test')}")
    print()

    # Test blocked actions
    print("Testing blocked actions:")
    print(f"  pay_invoice($50,000): {pay_invoice(vendor='Big Vendor', amount=50000)}")
    print(f"  send_email(spam.com): {send_email(to='user@spam.com', subject='Hello', body='Test')}")
    print()

    fw.close()


# ============================================================================
# Demo 2: Callback Handler Pattern
# ============================================================================

def demo_callback_handler():
    """Demonstrate the FirewallCallbackHandler pattern."""
    print("=" * 60)
    print("Demo 2: Callback Handler Pattern")
    print("=" * 60)
    print()

    fw = get_firewall()

    from callback_handler import FirewallCallbackHandler

    handler = FirewallCallbackHandler(fw, agent_name="demo_agent", raise_on_block=False)

    # Simulate tool calls (normally LangChain would do this)
    def simulate_tool_call(name: str, params: Dict):
        """Simulate what LangChain does when calling a tool."""
        import json
        serialized = {"name": name}
        input_str = json.dumps(params)

        try:
            handler.on_tool_start(serialized, input_str, inputs=params)
            print(f"  ✅ {name}: Allowed")
            return True
        except PermissionError as e:
            print(f"  🚫 {name}: {e}")
            return False

    print("Simulating tool calls through callback handler:")
    simulate_tool_call("pay_invoice", {"vendor": "Acme", "amount": 5000})
    simulate_tool_call("pay_invoice", {"vendor": "BigCorp", "amount": 50000})
    simulate_tool_call("send_email", {"to": "user@company.com", "subject": "Hi"})
    simulate_tool_call("execute_sql", {"query": "SELECT * FROM users"})
    print()

    # Show summary
    summary = handler.get_summary()
    print(f"Summary: {summary['allowed_count']} allowed, {summary['blocked_count']} blocked")
    print()

    fw.close()


# ============================================================================
# Demo 3: Protected Agent Pattern
# ============================================================================

def demo_protected_agent():
    """Demonstrate the ProtectedAgentExecutor pattern."""
    print("=" * 60)
    print("Demo 3: Protected Agent Executor Pattern")
    print("=" * 60)
    print()

    print("This pattern wraps an entire AgentExecutor to protect all tools.")
    print()
    print("Usage:")
    print("  from protected_agent import ProtectedAgentExecutor")
    print("  from ai_firewall import AIFirewall")
    print()
    print("  fw = AIFirewall(api_key='...', project_id='...')")
    print("  executor = AgentExecutor(agent=agent, tools=tools)")
    print("  protected = ProtectedAgentExecutor(executor, fw, 'my_agent')")
    print()
    print("  # Now all tool calls are automatically validated")
    print("  result = protected.invoke({'input': 'Pay invoice #123'})")
    print()
    print("  # Check what was blocked")
    print("  print(protected.get_blocked_actions())")
    print()


# ============================================================================
# Demo 4: Real LangChain Agent (requires LangChain + OpenAI)
# ============================================================================

def demo_real_agent():
    """Demonstrate with a real LangChain agent (if dependencies available)."""
    print("=" * 60)
    print("Demo 4: Real LangChain Agent")
    print("=" * 60)
    print()

    try:
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI
        from langchain.agents import create_tool_calling_agent, AgentExecutor
        from langchain_core.prompts import ChatPromptTemplate

        print("LangChain dependencies found!")
        print()
        print("To run a real agent, you need:")
        print("  1. OPENAI_API_KEY environment variable set")
        print("  2. AI Firewall server running")
        print("  3. A project with policies configured")
        print()
        print("Example code:")
        print("""
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from protected_agent import create_protected_agent

    @tool
    def pay_invoice(vendor: str, amount: float) -> str:
        \"\"\"Pay an invoice to a vendor.\"\"\"
        return f"Paid ${amount} to {vendor}"

    llm = ChatOpenAI(model="gpt-4")
    tools = [pay_invoice]

    # Create protected agent
    fw = AIFirewall(api_key="...", project_id="...")
    protected = create_protected_agent(
        agent=create_tool_calling_agent(llm, tools, prompt),
        tools=tools,
        firewall=fw,
        agent_name="finance_agent"
    )

    result = protected.invoke({"input": "Pay $500 to Acme Corp"})
        """)
        print()

    except ImportError as e:
        print(f"LangChain not fully installed: {e}")
        print()
        print("Install with: pip install langchain langchain-openai")
        print()


# ============================================================================
# Main
# ============================================================================

def main():
    print()
    print("🛡️  AI Firewall + LangChain Integration Demo")
    print("=" * 60)
    print()

    if MOCK_MODE:
        print("Mode: MOCK (no server required)")
    else:
        print("Mode: LIVE (requires AI Firewall server at localhost:8000)")
    print()

    demo_tool_wrapper()
    demo_callback_handler()
    demo_protected_agent()
    demo_real_agent()

    print("=" * 60)
    print("Demo complete!")
    print()
    print("Next steps:")
    print("  1. Review the code in this directory")
    print("  2. Read docs/integrations/langchain.md")
    print("  3. Integrate with your own LangChain agents")
    print()


if __name__ == "__main__":
    main()
