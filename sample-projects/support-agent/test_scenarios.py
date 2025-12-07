"""
Test Scenarios for Support Agent

Tests the firewall rules directly to show blocking behavior:
1. PII in response -> BLOCKED
2. Close ticket without review tag -> BLOCKED
3. Close ticket with review tag -> ALLOWED
4. Normal response -> ALLOWED
"""

import sys
sys.path.insert(0, "../../sdk/python")

from ai_firewall import AIFirewall
import httpx

FIREWALL_URL = "http://localhost:8000"


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
        sys.exit(1)

    # Create project
    import time
    project_id = f"support-test-{int(time.time())}"
    resp = client.post("/projects", json={"id": project_id, "name": "Test Project"})
    if resp.status_code != 200:
        print(f"ERROR: Failed to create project: {resp.text}")
        sys.exit(1)

    api_key = resp.json()["api_key"]

    # SSN pattern
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'

    # Create policy
    policy = {
        "name": "test-policy",
        "version": "1.0",
        "default": "block",
        "rules": [
            {
                "action_type": "send_response",
                "constraints": {
                    "params.response_text": {
                        "not_pattern": ssn_pattern,
                        "reason": "Response contains SSN - PII not allowed"
                    },
                },
                "allowed_agents": ["support_agent"],
            },
            {
                "action_type": "close_ticket",
                "constraints": {
                    "params.has_reviewed_tag": {"equals": True},
                },
                "allowed_agents": ["support_agent"],
            },
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
    """Run all test scenarios."""
    print("=" * 70)
    print(" SUPPORT AGENT - FIREWALL TEST SCENARIOS")
    print("=" * 70)
    print("\nThis test validates the FIREWALL rules directly.\n")

    # Setup
    print("[Setup] Creating test environment...")
    project_id, api_key = setup_test_environment()
    print(f"  Project: {project_id}")

    # Initialize firewall
    firewall = AIFirewall(
        api_key=api_key,
        project_id=project_id,
        base_url=FIREWALL_URL,
    )

    results = []

    # =========================================================================
    # Test 1: Normal response (no PII)
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 1: Normal response without PII")
    print("  Expected: ALLOWED")
    print("-" * 70)

    result = firewall.execute(
        agent_name="support_agent",
        action_type="send_response",
        params={
            "ticket_id": "TKT-001",
            "response_text": "Thank you for contacting support. We'll help you reset your password.",
        },
    )

    print(f"  Result: {'ALLOWED' if result.allowed else 'BLOCKED'}")
    print(f"  Reason: {result.reason or 'None'}")
    test_pass = result.allowed
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Normal response (no PII)", test_pass))

    # =========================================================================
    # Test 2: Response containing SSN (PII leak)
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 2: Response containing SSN - PII leak attempt")
    print("  Expected: BLOCKED")
    print("-" * 70)

    result = firewall.execute(
        agent_name="support_agent",
        action_type="send_response",
        params={
            "ticket_id": "TKT-002",
            "response_text": "I've updated your SSN to 123-45-6789 as requested.",
        },
    )

    print(f"  Result: {'ALLOWED' if result.allowed else 'BLOCKED'}")
    print(f"  Reason: {result.reason or 'None'}")
    test_pass = not result.allowed and "SSN" in (result.reason or "")
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Response with SSN blocked", test_pass))

    # =========================================================================
    # Test 3: Close ticket WITHOUT reviewed tag
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 3: Close ticket WITHOUT 'reviewed' tag")
    print("  Expected: BLOCKED")
    print("-" * 70)

    result = firewall.execute(
        agent_name="support_agent",
        action_type="close_ticket",
        params={
            "ticket_id": "TKT-003",
            "resolution": "Issue resolved",
            "has_reviewed_tag": False,  # No review tag!
        },
    )

    print(f"  Result: {'ALLOWED' if result.allowed else 'BLOCKED'}")
    print(f"  Reason: {result.reason or 'None'}")
    test_pass = not result.allowed
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Close without review tag blocked", test_pass))

    # =========================================================================
    # Test 4: Close ticket WITH reviewed tag
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 4: Close ticket WITH 'reviewed' tag")
    print("  Expected: ALLOWED")
    print("-" * 70)

    result = firewall.execute(
        agent_name="support_agent",
        action_type="close_ticket",
        params={
            "ticket_id": "TKT-004",
            "resolution": "Issue resolved",
            "has_reviewed_tag": True,  # Has review tag!
        },
    )

    print(f"  Result: {'ALLOWED' if result.allowed else 'BLOCKED'}")
    print(f"  Reason: {result.reason or 'None'}")
    test_pass = result.allowed
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Close with review tag allowed", test_pass))

    # =========================================================================
    # Test 5: Response with credit card number
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 5: Response containing email address")
    print("  Expected: ALLOWED (only SSN is blocked in this policy)")
    print("-" * 70)

    result = firewall.execute(
        agent_name="support_agent",
        action_type="send_response",
        params={
            "ticket_id": "TKT-005",
            "response_text": "Please contact support@company.com for further help.",
        },
    )

    print(f"  Result: {'ALLOWED' if result.allowed else 'BLOCKED'}")
    print(f"  Reason: {result.reason or 'None'}")
    test_pass = result.allowed  # Email is allowed in this policy
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Response with email allowed", test_pass))

    # =========================================================================
    # Test 6: Unauthorized agent trying to close ticket
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 6: Unauthorized agent trying to close ticket")
    print("  Expected: BLOCKED")
    print("-" * 70)

    result = firewall.execute(
        agent_name="random_agent",  # Not in allowed_agents
        action_type="close_ticket",
        params={
            "ticket_id": "TKT-006",
            "resolution": "Issue resolved",
            "has_reviewed_tag": True,
        },
    )

    print(f"  Result: {'ALLOWED' if result.allowed else 'BLOCKED'}")
    print(f"  Reason: {result.reason or 'None'}")
    test_pass = not result.allowed
    print(f"  Test: {'PASS' if test_pass else 'FAIL'}")
    results.append(("Unauthorized agent blocked", test_pass))

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print(" TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, p in results if p)
    failed = len(results) - passed

    for name, pass_fail in results:
        status = "PASS" if pass_fail else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\n  Total: {passed}/{len(results)} passed")

    if failed == 0:
        print("\n  ALL TESTS PASSED!")
    else:
        print(f"\n  {failed} test(s) failed")

    # Firewall stats
    print("\n" + "-" * 70)
    print(" FIREWALL STATS")
    print("-" * 70)
    stats = firewall.get_stats()
    print(f"  Total validations: {stats['total_actions']}")
    print(f"  Allowed: {stats['allowed']}")
    print(f"  Blocked: {stats['blocked']}")
    print(f"  Block rate: {stats['block_rate']}%")

    firewall.close()
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
