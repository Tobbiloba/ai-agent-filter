"""
Integration Tests for LangChain + AI Firewall

This script tests all three integration patterns to verify they work correctly.
Run this with the AI Firewall server running.

Usage:
    # With real firewall server
    python test_integration.py

    # With mock firewall (no server needed)
    python test_integration.py --mock
"""

import os
import sys
from typing import Any, Dict

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

MOCK_MODE = "--mock" in sys.argv


# ============================================================================
# Mock Firewall
# ============================================================================

class MockValidationResult:
    def __init__(self, allowed: bool, reason: str = None):
        self.allowed = allowed
        self.action_id = "act_mock123"
        self.reason = reason
        self.execution_time_ms = 1


class MockFirewall:
    """Mock firewall that simulates policy enforcement."""

    def __init__(self, **kwargs):
        self.max_payment = 10000
        self.allowed_currencies = ["USD", "EUR", "GBP"]
        self.allowed_email_domains = ["company.com", "example.com"]

    def execute(self, agent_name: str, action_type: str, params: Dict[str, Any] = None) -> MockValidationResult:
        params = params or {}

        if action_type == "pay_invoice":
            amount = params.get("amount", 0)
            currency = params.get("currency", "USD")

            if amount > self.max_payment:
                return MockValidationResult(False, f"Amount {amount} exceeds max {self.max_payment}")
            if currency not in self.allowed_currencies:
                return MockValidationResult(False, f"Currency {currency} not in {self.allowed_currencies}")

        elif action_type == "send_email":
            to = params.get("to", "")
            domain_ok = any(d in to for d in self.allowed_email_domains)
            if not domain_ok:
                return MockValidationResult(False, f"Email domain not allowed. Must be: {self.allowed_email_domains}")

        elif action_type == "execute_sql":
            return MockValidationResult(False, "SQL execution is blocked for all agents")

        return MockValidationResult(True)

    def close(self):
        pass


def get_firewall():
    if MOCK_MODE:
        print("🔸 Using MOCK firewall")
        return MockFirewall()
    else:
        from ai_firewall import AIFirewall
        api_key = os.getenv("FIREWALL_API_KEY", "")
        if not api_key:
            print("❌ FIREWALL_API_KEY not set. Run with --mock or set the key.")
            sys.exit(1)
        return AIFirewall(
            api_key=api_key,
            project_id=os.getenv("FIREWALL_PROJECT_ID", "langchain-demo"),
            base_url=os.getenv("FIREWALL_URL", "http://localhost:8000"),
        )


# ============================================================================
# Tests
# ============================================================================

def test_tool_wrapper():
    """Test Pattern 1: Tool Wrapper"""
    print("\n" + "=" * 60)
    print("Test: Tool Wrapper Pattern")
    print("=" * 60)

    from examples.langchain.tool_wrapper import protected_tool
    from tools import pay_invoice, send_email, execute_sql, reset_state

    reset_state()
    fw = get_firewall()

    # Wrap tools - use action_type parameter to match policy rules
    @protected_tool(fw, "test_agent", action_type="pay_invoice")
    def protected_pay(invoice_id: str, vendor: str, amount: float, currency: str = "USD"):
        return pay_invoice(invoice_id, vendor, amount, currency)

    @protected_tool(fw, "test_agent", action_type="send_email")
    def protected_email(to: str, subject: str, body: str):
        return send_email(to, subject, body)

    @protected_tool(fw, "test_agent", action_type="execute_sql")
    def protected_sql(query: str):
        return execute_sql(query)

    results = []

    # Test 1: Valid payment
    print("\n1. Valid payment ($5000 USD)...")
    result = protected_pay(invoice_id="INV-001", vendor="Acme", amount=5000, currency="USD")
    passed = "blocked" not in result.lower()
    results.append(("Valid payment", passed, result[:60]))
    print(f"   {'✅ PASS' if passed else '❌ FAIL'}: {result[:60]}")

    # Test 2: Payment too high
    print("\n2. Payment too high ($50000)...")
    result = protected_pay(invoice_id="INV-002", vendor="Acme", amount=50000, currency="USD")
    passed = "blocked" in result.lower()
    results.append(("High payment blocked", passed, result[:60]))
    print(f"   {'✅ PASS' if passed else '❌ FAIL'}: {result[:60]}")

    # Test 3: Valid email
    print("\n3. Valid email (to @company.com)...")
    result = protected_email(to="user@company.com", subject="Test", body="Hello")
    passed = "blocked" not in result.lower()
    results.append(("Valid email", passed, result[:60]))
    print(f"   {'✅ PASS' if passed else '❌ FAIL'}: {result[:60]}")

    # Test 4: Invalid email domain
    print("\n4. Invalid email (to @evil.com)...")
    result = protected_email(to="user@evil.com", subject="Test", body="Hello")
    passed = "blocked" in result.lower()
    results.append(("Bad email blocked", passed, result[:60]))
    print(f"   {'✅ PASS' if passed else '❌ FAIL'}: {result[:60]}")

    # Test 5: SQL blocked
    print("\n5. SQL execution (should be blocked)...")
    result = protected_sql(query="SELECT * FROM users")
    passed = "blocked" in result.lower()
    results.append(("SQL blocked", passed, result[:60]))
    print(f"   {'✅ PASS' if passed else '❌ FAIL'}: {result[:60]}")

    fw.close()
    return results


def test_callback_handler():
    """Test Pattern 2: Callback Handler"""
    print("\n" + "=" * 60)
    print("Test: Callback Handler Pattern")
    print("=" * 60)

    from examples.langchain.callback_handler import FirewallCallbackHandler
    import json

    fw = get_firewall()
    handler = FirewallCallbackHandler(fw, agent_name="test_agent", raise_on_block=False)

    results = []

    def simulate_tool(name: str, params: dict):
        """Simulate LangChain calling a tool."""
        serialized = {"name": name}
        handler.on_tool_start(serialized, json.dumps(params), inputs=params)

    # Test 1: Valid action
    print("\n1. Valid payment via callback...")
    handler.reset()
    simulate_tool("pay_invoice", {"amount": 5000, "currency": "USD"})
    passed = len(handler.blocked_actions) == 0
    results.append(("Callback allows valid", passed, f"Blocked: {len(handler.blocked_actions)}"))
    print(f"   {'✅ PASS' if passed else '❌ FAIL'}: {len(handler.blocked_actions)} blocked")

    # Test 2: Blocked action
    print("\n2. High payment via callback...")
    handler.reset()
    simulate_tool("pay_invoice", {"amount": 50000, "currency": "USD"})
    passed = len(handler.blocked_actions) == 1
    results.append(("Callback blocks invalid", passed, f"Blocked: {len(handler.blocked_actions)}"))
    print(f"   {'✅ PASS' if passed else '❌ FAIL'}: {len(handler.blocked_actions)} blocked")

    # Test 3: Summary
    print("\n3. Testing summary...")
    handler.reset()
    simulate_tool("pay_invoice", {"amount": 1000, "currency": "USD"})
    simulate_tool("pay_invoice", {"amount": 50000, "currency": "USD"})
    simulate_tool("send_email", {"to": "user@company.com"})
    summary = handler.get_summary()
    passed = summary["allowed_count"] == 2 and summary["blocked_count"] == 1
    results.append(("Summary correct", passed, f"Summary: {summary['allowed_count']}✓ {summary['blocked_count']}✗"))
    print(f"   {'✅ PASS' if passed else '❌ FAIL'}: {summary}")

    fw.close()
    return results


def test_protected_executor():
    """Test Pattern 3: Protected Executor (structure only, no LLM needed)"""
    print("\n" + "=" * 60)
    print("Test: Protected Executor Pattern")
    print("=" * 60)

    from examples.langchain.protected_agent import ProtectedAgentExecutor

    results = []

    # Test that the class is importable and constructable
    print("\n1. Testing class structure...")
    try:
        # We can't fully test without LangChain + LLM, but we can verify structure
        fw = get_firewall()

        # Check methods exist
        assert hasattr(ProtectedAgentExecutor, 'invoke')
        assert hasattr(ProtectedAgentExecutor, 'ainvoke')
        assert hasattr(ProtectedAgentExecutor, 'stream')
        assert hasattr(ProtectedAgentExecutor, 'get_blocked_actions')
        assert hasattr(ProtectedAgentExecutor, 'get_summary')

        results.append(("Executor structure", True, "All methods present"))
        print("   ✅ PASS: All required methods present")

        fw.close()
    except Exception as e:
        results.append(("Executor structure", False, str(e)[:50]))
        print(f"   ❌ FAIL: {e}")

    return results


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("🧪 LangChain + AI Firewall Integration Tests")
    print("=" * 60)

    if MOCK_MODE:
        print("\nMode: MOCK (no server required)")
    else:
        print("\nMode: LIVE (requires AI Firewall server)")

    all_results = []

    # Run tests
    all_results.extend(test_tool_wrapper())
    all_results.extend(test_callback_handler())
    all_results.extend(test_protected_executor())

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(1 for _, p, _ in all_results if p)
    total = len(all_results)

    for name, success, detail in all_results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}: {detail}")

    print()
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
