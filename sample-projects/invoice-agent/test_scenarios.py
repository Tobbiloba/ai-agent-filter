"""
Test Scenarios for Invoice Payment Agent

Runs through all test cases to verify the firewall integration works correctly.
Uses a deterministic agent (no LLM) to ensure consistent test results.
"""

import sys
import httpx

# Add parent directory for ai_firewall import
sys.path.insert(0, "../../sdk/python")

from ai_firewall import AIFirewall
from payment_system import PaymentSystem


FIREWALL_URL = "http://localhost:8000"
PROJECT_ID = "invoice-test"


class TestInvoice:
    """Invoice for testing."""
    def __init__(self, id: str, vendor: str, amount: float, description: str = ""):
        self.id = id
        self.vendor = vendor
        self.amount = amount
        self.description = description
        self.currency = "USD"


def setup_test_environment():
    """Create a fresh project and policy for testing."""
    client = httpx.Client(base_url=FIREWALL_URL, timeout=10)

    # Check firewall is running
    try:
        resp = client.get("/health")
        if resp.status_code != 200:
            print("ERROR: Firewall not healthy")
            sys.exit(1)
    except httpx.ConnectError:
        print("ERROR: Cannot connect to firewall at", FIREWALL_URL)
        print("Start it with: uvicorn server.app:app --port 8000")
        sys.exit(1)

    # Create project
    import time
    project_id = f"{PROJECT_ID}-{int(time.time())}"
    resp = client.post("/projects", json={"id": project_id, "name": "Test Project"})
    if resp.status_code != 200:
        print(f"ERROR: Failed to create project: {resp.text}")
        sys.exit(1)

    api_key = resp.json()["api_key"]

    # Create policy with strict rules
    policy = {
        "name": "test-policy",
        "version": "1.0",
        "default": "block",
        "rules": [
            {
                "action_type": "pay_invoice",
                "constraints": {
                    "params.amount": {"max": 500, "min": 1},
                    "params.vendor": {"in": ["VendorA", "VendorB", "VendorC"]}
                },
                "allowed_agents": ["invoice_agent"],
                "rate_limit": {"max_requests": 10, "window_seconds": 60}
            }
        ]
    }

    resp = client.post(
        f"/policies/{project_id}",
        json=policy,
        headers={"X-API-Key": api_key}
    )
    if resp.status_code != 200:
        print(f"ERROR: Failed to create policy: {resp.text}")
        sys.exit(1)

    client.close()
    return project_id, api_key


def run_tests():
    """Run all test scenarios with deterministic behavior."""
    print("="*70)
    print(" INVOICE AGENT - FIREWALL TEST SCENARIOS")
    print("="*70)
    print("\nThis test validates the FIREWALL, not the AI.")
    print("All invoices are sent directly to the firewall for validation.\n")

    # Setup
    print("[Setup] Creating test environment...")
    project_id, api_key = setup_test_environment()
    print(f"  Project: {project_id}")
    print(f"  API Key: {api_key[:20]}...")

    # Initialize components
    firewall = AIFirewall(
        api_key=api_key,
        project_id=project_id,
        base_url=FIREWALL_URL,
    )
    payment_system = PaymentSystem()

    results = []

    def process_payment(invoice: TestInvoice, expected_allowed: bool, expected_reason: str = None):
        """Process a payment and return pass/fail."""
        # Check duplicate first
        if payment_system.is_duplicate(invoice.vendor, invoice.amount, invoice.id):
            allowed = False
            reason = "duplicate"
            message = "Duplicate invoice"
        else:
            # Validate with firewall
            result = firewall.execute(
                agent_name="invoice_agent",
                action_type="pay_invoice",
                params={
                    "vendor": invoice.vendor,
                    "amount": invoice.amount,
                    "invoice_id": invoice.id,
                },
            )
            allowed = result.allowed
            reason = result.reason or ""
            message = reason if not allowed else "Allowed"

            # Execute if allowed
            if allowed:
                payment_result = payment_system.process_payment(
                    vendor=invoice.vendor,
                    amount=invoice.amount,
                    invoice_id=invoice.id,
                )
                message = payment_result.message

        # Check result
        if expected_allowed:
            test_pass = allowed
        else:
            test_pass = not allowed
            if expected_reason:
                test_pass = test_pass and (expected_reason.lower() in reason.lower() or expected_reason.lower() in message.lower())

        return test_pass, allowed, message

    # =========================================================================
    # Test 1: Valid payment ($450 to VendorA)
    # =========================================================================
    print("\n" + "-"*70)
    print("TEST 1: Valid payment - $450 to VendorA")
    print("  Expected: ALLOWED")
    print("-"*70)

    invoice = TestInvoice("INV-001", "VendorA", 450.00, "Office supplies")
    test_pass, allowed, message = process_payment(invoice, expected_allowed=True)

    status = "ALLOWED" if allowed else "BLOCKED"
    print(f"  Result: {status}")
    print(f"  Message: {message}")
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Valid payment $450 to VendorA", test_pass))

    # =========================================================================
    # Test 2: Amount too high ($600)
    # =========================================================================
    print("\n" + "-"*70)
    print("TEST 2: Amount too high - $600 to VendorA")
    print("  Expected: BLOCKED (exceeds $500 max)")
    print("-"*70)

    invoice = TestInvoice("INV-002", "VendorA", 600.00, "Premium equipment")
    test_pass, allowed, message = process_payment(invoice, expected_allowed=False, expected_reason="exceeds maximum")

    status = "ALLOWED" if allowed else "BLOCKED"
    print(f"  Result: {status}")
    print(f"  Message: {message}")
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Amount too high $600", test_pass))

    # =========================================================================
    # Test 3: Unknown vendor
    # =========================================================================
    print("\n" + "-"*70)
    print("TEST 3: Unknown vendor - $100 to UnknownCorp")
    print("  Expected: BLOCKED (vendor not in approved list)")
    print("-"*70)

    invoice = TestInvoice("INV-003", "UnknownCorp", 100.00, "Mystery services")
    test_pass, allowed, message = process_payment(invoice, expected_allowed=False, expected_reason="not in allowed")

    status = "ALLOWED" if allowed else "BLOCKED"
    print(f"  Result: {status}")
    print(f"  Message: {message}")
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Unknown vendor", test_pass))

    # =========================================================================
    # Test 4: Duplicate invoice
    # =========================================================================
    print("\n" + "-"*70)
    print("TEST 4: Duplicate invoice - INV-001 again")
    print("  Expected: BLOCKED (already paid)")
    print("-"*70)

    invoice = TestInvoice("INV-001", "VendorA", 450.00, "Office supplies")
    test_pass, allowed, message = process_payment(invoice, expected_allowed=False, expected_reason="duplicate")

    status = "ALLOWED" if allowed else "BLOCKED"
    print(f"  Result: {status}")
    print(f"  Message: {message}")
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Duplicate invoice", test_pass))

    # =========================================================================
    # Test 5: Amount at exactly the limit ($500)
    # =========================================================================
    print("\n" + "-"*70)
    print("TEST 5: Amount at limit - $500 to VendorB")
    print("  Expected: ALLOWED (exactly at limit)")
    print("-"*70)

    invoice = TestInvoice("INV-005", "VendorB", 500.00, "At the limit")
    test_pass, allowed, message = process_payment(invoice, expected_allowed=True)

    status = "ALLOWED" if allowed else "BLOCKED"
    print(f"  Result: {status}")
    print(f"  Message: {message}")
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Amount at limit $500", test_pass))

    # =========================================================================
    # Test 6: Amount just over limit ($501)
    # =========================================================================
    print("\n" + "-"*70)
    print("TEST 6: Amount over limit - $501 to VendorB")
    print("  Expected: BLOCKED (exceeds max)")
    print("-"*70)

    invoice = TestInvoice("INV-006", "VendorB", 501.00, "Over the limit")
    test_pass, allowed, message = process_payment(invoice, expected_allowed=False, expected_reason="exceeds")

    status = "ALLOWED" if allowed else "BLOCKED"
    print(f"  Result: {status}")
    print(f"  Message: {message}")
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Amount over limit $501", test_pass))

    # =========================================================================
    # Test 7: Valid payment to VendorC
    # =========================================================================
    print("\n" + "-"*70)
    print("TEST 7: Valid payment - $299.99 to VendorC")
    print("  Expected: ALLOWED")
    print("-"*70)

    invoice = TestInvoice("INV-007", "VendorC", 299.99, "Subscription")
    test_pass, allowed, message = process_payment(invoice, expected_allowed=True)

    status = "ALLOWED" if allowed else "BLOCKED"
    print(f"  Result: {status}")
    print(f"  Message: {message}")
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Valid payment $299.99 to VendorC", test_pass))

    # =========================================================================
    # Test 8: Amount below minimum ($0.50)
    # =========================================================================
    print("\n" + "-"*70)
    print("TEST 8: Amount below minimum - $0.50 to VendorA")
    print("  Expected: BLOCKED (below $1 min)")
    print("-"*70)

    invoice = TestInvoice("INV-008", "VendorA", 0.50, "Too small")
    test_pass, allowed, message = process_payment(invoice, expected_allowed=False, expected_reason="below minimum")

    status = "ALLOWED" if allowed else "BLOCKED"
    print(f"  Result: {status}")
    print(f"  Message: {message}")
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Amount below minimum $0.50", test_pass))

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, p in results if p)
    failed = len(results) - passed

    for name, pass_fail in results:
        status = "PASS" if pass_fail else "FAIL"
        icon = "" if pass_fail else ""
        print(f"  [{status}] {name}")

    print(f"\n  Total: {passed}/{len(results)} passed")

    if failed == 0:
        print("\n  ALL TESTS PASSED!")
    else:
        print(f"\n  {failed} test(s) failed")

    # Show payment history
    print("\n" + "-"*70)
    print(" PAYMENT HISTORY (Successful Payments)")
    print("-"*70)
    history = payment_system.get_transaction_history()
    if history:
        for txn in history:
            print(f"  {txn['transaction_id']}: ${txn['amount']:.2f} to {txn['vendor']}")
        print(f"\n  Total paid: ${payment_system.get_total_paid():.2f}")
    else:
        print("  No payments executed")

    # Show firewall stats
    print("\n" + "-"*70)
    print(" FIREWALL STATS")
    print("-"*70)
    stats = firewall.get_stats()
    print(f"  Total validations: {stats['total_actions']}")
    print(f"  Allowed: {stats['allowed']}")
    print(f"  Blocked: {stats['blocked']}")
    print(f"  Block rate: {stats['block_rate']}%")

    # Cleanup
    firewall.close()

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
