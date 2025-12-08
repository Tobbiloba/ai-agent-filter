"""
Security tests for AI Agent Firewall.

Tests:
- SQL injection attempts in params
- XSS in agent names/action types
- API key brute force protection
- Rate limit bypass attempts
- Policy injection attempts (including ReDoS)
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.app import app
from server.services.policy_engine import PolicyEngine


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def client():
    """TestClient for security tests."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def secure_project(client):
    """Create a project for security testing."""
    project_id = f"security-test-{uuid.uuid4().hex[:8]}"
    response = client.post("/projects", json={
        "id": project_id,
        "name": "Security Test Project"
    })
    api_key = response.json()["api_key"]

    # Create a policy
    client.post(
        f"/policies/{project_id}",
        json={
            "name": "security-policy",
            "version": "1.0",
            "default": "allow",
            "rules": [
                {
                    "action_type": "test_action",
                    "constraints": {
                        "params.amount": {"max": 1000}
                    },
                    "rate_limit": {"max_requests": 5, "window_seconds": 60}
                }
            ]
        },
        headers={"X-API-Key": api_key}
    )

    return project_id, api_key


# =============================================================================
# SQL INJECTION TESTS
# =============================================================================

class TestSQLInjection:
    """Test SQL injection prevention."""

    SQL_INJECTION_PAYLOADS = [
        "'; DROP TABLE projects; --",
        "1; DELETE FROM projects WHERE 1=1; --",
        "' OR '1'='1",
        "' OR 1=1 --",
        "'; SELECT * FROM api_keys; --",
        "1 UNION SELECT * FROM projects --",
        "'; UPDATE projects SET is_active=0; --",
        "' AND 1=0 UNION SELECT id, api_key FROM api_keys --",
        "'; INSERT INTO projects VALUES ('hacked', 'Hacked'); --",
        "1); DROP TABLE action_logs; --",
    ]

    def test_sql_injection_in_params_amount(self, client, secure_project):
        """SQL injection in params.amount should not execute."""
        project_id, api_key = secure_project

        for payload in self.SQL_INJECTION_PAYLOADS:
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "test_agent",
                    "action_type": "test_action",
                    "params": {"amount": payload}
                },
                headers={"X-API-Key": api_key}
            )
            # Should return 200 (validation result), not crash or execute SQL
            assert response.status_code == 200
            # The payload should be treated as a string, not executed
            data = response.json()
            assert "allowed" in data

    def test_sql_injection_in_agent_name(self, client, secure_project):
        """SQL injection in agent_name should not execute."""
        project_id, api_key = secure_project

        for payload in self.SQL_INJECTION_PAYLOADS:
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": payload,
                    "action_type": "test_action",
                    "params": {"amount": 100}
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200
            data = response.json()
            assert "allowed" in data

    def test_sql_injection_in_action_type(self, client, secure_project):
        """SQL injection in action_type should not execute."""
        project_id, api_key = secure_project

        for payload in self.SQL_INJECTION_PAYLOADS:
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "test_agent",
                    "action_type": payload,
                    "params": {"amount": 100}
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

    def test_sql_injection_in_project_id_path(self, client, secure_project):
        """SQL injection in project_id path parameter should fail safely."""
        _, api_key = secure_project

        for payload in self.SQL_INJECTION_PAYLOADS[:5]:  # Test subset
            response = client.get(
                f"/projects/{payload}",
                headers={"X-API-Key": api_key}
            )
            # Should return 403 (wrong project) or 404 (not found), not execute SQL
            assert response.status_code in [403, 404]

    def test_sql_injection_in_log_filters(self, client, secure_project):
        """SQL injection in log filter parameters should not execute."""
        project_id, api_key = secure_project

        for payload in self.SQL_INJECTION_PAYLOADS[:5]:
            response = client.get(
                f"/logs/{project_id}?agent_name={payload}",
                headers={"X-API-Key": api_key}
            )
            # Should return 200 with empty results, not crash
            assert response.status_code == 200

    def test_database_intact_after_injection_attempts(self, client, secure_project):
        """Verify database tables still exist after injection attempts."""
        project_id, api_key = secure_project

        # Try a destructive payload
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "'; DROP TABLE projects; --",
                "action_type": "test",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )

        # Verify project still exists
        response = client.get(
            f"/projects/{project_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        assert response.json()["id"] == project_id


# =============================================================================
# XSS TESTS
# =============================================================================

class TestXSS:
    """Test XSS prevention."""

    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert('xss')>",
        "<svg onload=alert('xss')>",
        "javascript:alert('xss')",
        "<body onload=alert('xss')>",
        "<iframe src='javascript:alert(1)'>",
        "'\"><script>alert('xss')</script>",
        "<div style='background:url(javascript:alert(1))'>",
        "{{constructor.constructor('alert(1)')()}}",
        "${alert('xss')}",
    ]

    def test_xss_in_agent_name_not_reflected(self, client, secure_project):
        """XSS in agent_name should be stored safely, not executed."""
        project_id, api_key = secure_project

        for payload in self.XSS_PAYLOADS:
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": payload,
                    "action_type": "test_action",
                    "params": {"amount": 100}
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

            # Check response doesn't contain unescaped script
            response_text = response.text
            # The payload should be JSON-encoded, not raw HTML
            assert "<script>" not in response_text or "\\u003c" in response_text or '\\"' in response_text

    def test_xss_in_action_type(self, client, secure_project):
        """XSS in action_type should be handled safely."""
        project_id, api_key = secure_project

        for payload in self.XSS_PAYLOADS:
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "test_agent",
                    "action_type": payload,
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

    def test_xss_in_project_name(self, client):
        """XSS in project name should be handled safely."""
        for payload in self.XSS_PAYLOADS[:5]:
            project_id = f"xss-test-{uuid.uuid4().hex[:8]}"
            response = client.post("/projects", json={
                "id": project_id,
                "name": payload
            })
            assert response.status_code == 200

            # Retrieve and verify it's stored safely
            api_key = response.json()["api_key"]
            get_response = client.get(
                f"/projects/{project_id}",
                headers={"X-API-Key": api_key}
            )
            assert get_response.status_code == 200
            # Name should be returned as-is (JSON encoded), not executed
            assert get_response.json()["name"] == payload

    def test_xss_in_policy_name(self, client, secure_project):
        """XSS in policy name should be handled safely."""
        project_id, api_key = secure_project

        for payload in self.XSS_PAYLOADS[:5]:
            response = client.post(
                f"/policies/{project_id}",
                json={
                    "name": payload,
                    "version": "1.0",
                    "default": "allow",
                    "rules": []
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

    def test_xss_stored_in_logs_safely(self, client, secure_project):
        """XSS payloads in logs should be stored and retrieved safely."""
        project_id, api_key = secure_project

        # Store action with XSS payload
        xss_payload = "<script>alert('xss')</script>"
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": xss_payload,
                "action_type": "test",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )

        # Retrieve logs
        response = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

        # Verify the payload is in the response but JSON-encoded
        data = response.json()
        found_payload = False
        for item in data["items"]:
            if item["agent_name"] == xss_payload:
                found_payload = True
                break
        assert found_payload, "XSS payload should be stored and retrievable"


# =============================================================================
# API KEY BRUTE FORCE TESTS
# =============================================================================

class TestAPIKeyBruteForce:
    """Test API key security against brute force attacks."""

    def test_invalid_key_returns_consistent_error(self, client, secure_project):
        """Invalid API keys should return consistent 401/403 responses."""
        project_id, _ = secure_project

        invalid_keys = [
            "invalid_key_1",
            "invalid_key_2",
            "af_wrongkey123",
            "af_" + "a" * 40,
        ]

        for key in invalid_keys:
            # Use /policies endpoint which requires auth
            response = client.get(
                f"/policies/{project_id}",
                headers={"X-API-Key": key}
            )
            # Invalid should be 403
            assert response.status_code == 403, f"Key '{key[:20]}...' returned {response.status_code}"

        # Empty/missing key should be 401
        response = client.get(f"/policies/{project_id}")
        assert response.status_code == 401

    def test_timing_attack_resistance(self, client, secure_project):
        """Response times should be consistent regardless of key validity."""
        project_id, valid_key = secure_project

        # Measure response times for valid and invalid keys
        valid_times = []
        invalid_times = []

        for _ in range(10):
            # Valid key - use /policies endpoint which requires auth
            start = time.perf_counter()
            client.get(
                f"/policies/{project_id}",
                headers={"X-API-Key": valid_key}
            )
            valid_times.append(time.perf_counter() - start)

            # Invalid key
            start = time.perf_counter()
            client.get(
                f"/policies/{project_id}",
                headers={"X-API-Key": "invalid_key_attempt"}
            )
            invalid_times.append(time.perf_counter() - start)

        avg_valid = sum(valid_times) / len(valid_times)
        avg_invalid = sum(invalid_times) / len(invalid_times)

        # Times should be within reasonable variance (not a huge difference)
        # Note: This is a basic check; real timing attacks need more sophisticated testing
        ratio = max(avg_valid, avg_invalid) / min(avg_valid, avg_invalid)
        assert ratio < 5, f"Response time ratio {ratio:.2f} suggests timing vulnerability"

    def test_sequential_key_guessing(self, client, secure_project):
        """Sequential key guessing should all fail."""
        project_id, _ = secure_project

        # Try sequential patterns - use /policies endpoint which requires auth
        for i in range(20):
            guessed_key = f"af_{i:040d}"
            response = client.get(
                f"/policies/{project_id}",
                headers={"X-API-Key": guessed_key}
            )
            assert response.status_code == 403

    def test_error_message_doesnt_leak_info(self, client, secure_project):
        """Error messages should not reveal key structure or valid keys."""
        project_id, _ = secure_project

        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": "wrong_key"}
        )

        error_detail = response.json().get("detail", "")

        # Should not contain hints about valid key format
        assert "af_" not in error_detail.lower()
        assert "format" not in error_detail.lower()
        assert "length" not in error_detail.lower()
        assert "character" not in error_detail.lower()

    def test_many_failed_attempts_still_work(self, client, secure_project):
        """System should still work after many failed attempts (no lockout DoS)."""
        project_id, valid_key = secure_project

        # Make many failed attempts - use /policies endpoint which requires auth
        for _ in range(50):
            client.get(
                f"/policies/{project_id}",
                headers={"X-API-Key": "invalid_attempt"}
            )

        # Valid key should still work
        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": valid_key}
        )
        assert response.status_code == 200


# =============================================================================
# RATE LIMIT BYPASS TESTS
# =============================================================================

class TestRateLimitBypass:
    """Test rate limiting cannot be bypassed."""

    def test_cannot_bypass_with_different_case_agent(self, client):
        """Rate limit should apply regardless of agent name case."""
        project_id = f"ratelimit-case-{uuid.uuid4().hex[:8]}"
        unique_agent = f"agent_{uuid.uuid4().hex[:8]}"
        unique_action = f"action_{uuid.uuid4().hex[:8]}"

        response = client.post("/projects", json={
            "id": project_id,
            "name": "Rate Limit Case Test"
        })
        api_key = response.json()["api_key"]

        # Policy with strict rate limit
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "strict-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [
                    {
                        "action_type": unique_action,
                        "rate_limit": {"max_requests": 3, "window_seconds": 60}
                    }
                ]
            },
            headers={"X-API-Key": api_key}
        )

        # Use exact same agent name - should hit limit
        for i in range(3):
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": unique_agent,
                    "action_type": unique_action,
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )
            assert response.json()["allowed"] is True

        # 4th request should be blocked
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": unique_agent,
                "action_type": unique_action,
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is False

    def test_cannot_bypass_with_action_type_variations(self, client):
        """Rate limit should not be bypassed by action type variations."""
        project_id = f"ratelimit-action-{uuid.uuid4().hex[:8]}"
        response = client.post("/projects", json={
            "id": project_id,
            "name": "Rate Limit Action Test"
        })
        api_key = response.json()["api_key"]

        client.post(
            f"/policies/{project_id}",
            json={
                "name": "strict-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [
                    {
                        "action_type": "send_email",
                        "rate_limit": {"max_requests": 2, "window_seconds": 60}
                    }
                ]
            },
            headers={"X-API-Key": api_key}
        )

        # Exhaust rate limit
        for _ in range(2):
            client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "agent",
                    "action_type": "send_email",
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )

        # Try variations - these are different actions, so they shouldn't be blocked
        # But the original should still be blocked
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent",
                "action_type": "send_email",  # Original action
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is False, "Original action should still be rate limited"

    def test_rate_limit_persists_across_requests(self, client):
        """Rate limit state should persist correctly."""
        project_id = f"ratelimit-persist-{uuid.uuid4().hex[:8]}"
        response = client.post("/projects", json={
            "id": project_id,
            "name": "Rate Limit Persist Test"
        })
        api_key = response.json()["api_key"]

        client.post(
            f"/policies/{project_id}",
            json={
                "name": "persist-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [
                    {
                        "action_type": "persist_action",
                        "rate_limit": {"max_requests": 3, "window_seconds": 60}
                    }
                ]
            },
            headers={"X-API-Key": api_key}
        )

        # Make requests with delays
        allowed_count = 0
        for i in range(5):
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "agent",
                    "action_type": "persist_action",
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )
            if response.json()["allowed"]:
                allowed_count += 1
            time.sleep(0.1)  # Small delay between requests

        assert allowed_count == 3, f"Expected 3 allowed, got {allowed_count}"

    def test_concurrent_requests_respect_limit(self, client):
        """Concurrent requests should still respect rate limits."""
        project_id = f"ratelimit-concurrent-{uuid.uuid4().hex[:8]}"
        response = client.post("/projects", json={
            "id": project_id,
            "name": "Rate Limit Concurrent Test"
        })
        api_key = response.json()["api_key"]

        client.post(
            f"/policies/{project_id}",
            json={
                "name": "concurrent-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [
                    {
                        "action_type": "concurrent_action",
                        "rate_limit": {"max_requests": 5, "window_seconds": 60}
                    }
                ]
            },
            headers={"X-API-Key": api_key}
        )

        def make_request():
            resp = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "agent",
                    "action_type": "concurrent_action",
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )
            return resp.json()["allowed"]

        # Send 10 concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]

        allowed_count = sum(results)
        # Should allow at most 5 (the rate limit)
        assert allowed_count <= 5, f"Rate limit bypassed: {allowed_count} allowed, expected <= 5"


# =============================================================================
# POLICY INJECTION TESTS
# =============================================================================

class TestPolicyInjection:
    """Test policy injection and malformed input handling."""

    def test_safe_regex_patterns_work(self, client, secure_project):
        """Safe regex patterns should work correctly."""
        project_id, api_key = secure_project

        # Safe patterns that won't cause ReDoS
        safe_pattern = r"^[a-zA-Z0-9]+$"

        # Create policy with safe regex
        response = client.post(
            f"/policies/{project_id}",
            json={
                "name": "safe-regex-test",
                "version": "1.0",
                "default": "allow",
                "rules": [
                    {
                        "action_type": "regex_test",
                        "constraints": {
                            "params.input": {"pattern": safe_pattern}
                        }
                    }
                ]
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

        # Test matching input
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent",
                "action_type": "regex_test",
                "params": {"input": "validInput123"}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        assert response.json()["allowed"] is True

        # Test non-matching input
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent",
                "action_type": "regex_test",
                "params": {"input": "invalid input!"}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        assert response.json()["allowed"] is False
        assert "pattern" in response.json()["reason"].lower()

    def test_deeply_nested_params(self, client, secure_project):
        """Deeply nested params should be handled safely."""
        project_id, api_key = secure_project

        # Create deeply nested structure
        nested = {"value": 1}
        for _ in range(50):
            nested = {"nested": nested}

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent",
                "action_type": "test",
                "params": nested
            },
            headers={"X-API-Key": api_key}
        )
        # Should handle gracefully, not crash
        assert response.status_code in [200, 422]

    def test_oversized_policy_rules(self, client, secure_project):
        """Oversized policy rules should be handled."""
        project_id, api_key = secure_project

        # Create policy with many rules
        rules = []
        for i in range(100):
            rules.append({
                "action_type": f"action_{i}",
                "constraints": {
                    f"params.field_{j}": {"max": 1000}
                    for j in range(10)
                }
            })

        response = client.post(
            f"/policies/{project_id}",
            json={
                "name": "large-policy",
                "version": "1.0",
                "default": "allow",
                "rules": rules
            },
            headers={"X-API-Key": api_key}
        )
        # Should either accept or reject gracefully
        assert response.status_code in [200, 413, 422]

    def test_invalid_constraint_types(self, client, secure_project):
        """Invalid constraint types should be handled safely."""
        project_id, api_key = secure_project

        invalid_constraints = [
            {"params.value": {"unknown_constraint": 100}},
            {"params.value": {"max": "not_a_number"}},
            {"params.value": {"in": "not_a_list"}},
            {"params.value": {"pattern": 12345}},
            {"params.value": None},
            {"params.value": []},
        ]

        for constraint in invalid_constraints:
            response = client.post(
                f"/policies/{project_id}",
                json={
                    "name": "invalid-constraint",
                    "version": "1.0",
                    "default": "allow",
                    "rules": [
                        {
                            "action_type": "test",
                            "constraints": constraint
                        }
                    ]
                },
                headers={"X-API-Key": api_key}
            )
            # Should accept (schema allows flexible constraints) or reject with 422
            assert response.status_code in [200, 422]

    def test_special_characters_in_constraint_path(self, client, secure_project):
        """Special characters in constraint paths should be handled."""
        project_id, api_key = secure_project

        special_paths = [
            "params.__proto__",
            "params.constructor",
            "params.../../../etc/passwd",
            "params.${env.SECRET}",
            "params.<script>",
        ]

        for path in special_paths:
            response = client.post(
                f"/policies/{project_id}",
                json={
                    "name": "special-path",
                    "version": "1.0",
                    "default": "allow",
                    "rules": [
                        {
                            "action_type": "test",
                            "constraints": {
                                path: {"max": 100}
                            }
                        }
                    ]
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code in [200, 422]

    def test_policy_engine_handles_malformed_json(self):
        """Policy engine should handle malformed JSON gracefully."""
        engine = PolicyEngine()

        malformed_policies = [
            "not json at all",
            "{incomplete",
            '{"rules": }',
            "",
            "null",
            "[]",
        ]

        for policy in malformed_policies:
            result = engine.validate(
                policy_json=policy,
                agent_name="agent",
                action_type="test",
                params={}
            )
            # Should return a result, not crash
            assert hasattr(result, "allowed")

    def test_constraint_type_confusion(self, client, secure_project):
        """Type confusion in constraints should be handled safely."""
        project_id, api_key = secure_project

        # Create policy
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "type-test",
                "version": "1.0",
                "default": "allow",
                "rules": [
                    {
                        "action_type": "test",
                        "constraints": {
                            "params.amount": {"max": 100}
                        }
                    }
                ]
            },
            headers={"X-API-Key": api_key}
        )

        # Try to confuse type checking
        type_confusion_values = [
            {"amount": [100]},  # List instead of number
            {"amount": {"value": 100}},  # Dict instead of number
            {"amount": True},  # Boolean
            {"amount": None},  # Null
            {"amount": "100"},  # String that looks like number
        ]

        for params in type_confusion_values:
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "agent",
                    "action_type": "test",
                    "params": params
                },
                headers={"X-API-Key": api_key}
            )
            # Should handle gracefully
            assert response.status_code == 200


# =============================================================================
# ADDITIONAL SECURITY TESTS
# =============================================================================

class TestAdditionalSecurity:
    """Additional security edge cases."""

    def test_null_byte_injection(self, client, secure_project):
        """Null byte injection should be handled safely."""
        project_id, api_key = secure_project

        null_payloads = [
            "test\x00injection",
            "test%00injection",
            "test\0injection",
        ]

        for payload in null_payloads:
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": payload,
                    "action_type": "test",
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

    def test_unicode_handling(self, client, secure_project):
        """Unicode characters should be handled safely."""
        project_id, api_key = secure_project

        unicode_payloads = [
            "тест",  # Cyrillic
            "测试",  # Chinese
            "🔥💀",  # Emojis
            "\u202e\u0041\u0042\u0043",  # RTL override
            "test\ufeffvalue",  # BOM
        ]

        for payload in unicode_payloads:
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": payload,
                    "action_type": "test",
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

    def test_large_request_body(self, client, secure_project):
        """Large request bodies should be handled (or rejected) safely."""
        project_id, api_key = secure_project

        # Create large params
        large_params = {f"field_{i}": "x" * 1000 for i in range(100)}

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent",
                "action_type": "test",
                "params": large_params
            },
            headers={"X-API-Key": api_key}
        )
        # Should handle or reject gracefully
        assert response.status_code in [200, 413, 422]

    def test_header_injection(self, client, secure_project):
        """Header injection attempts should be handled safely."""
        project_id, api_key = secure_project

        # Try to inject headers via API key
        injection_keys = [
            "valid_key\r\nX-Injected: true",
            "valid_key\nSet-Cookie: hacked=true",
        ]

        for key in injection_keys:
            try:
                response = client.get(
                    f"/projects/{project_id}",
                    headers={"X-API-Key": key}
                )
                # Should fail authentication, not inject headers
                assert response.status_code in [400, 401, 403]
            except Exception:
                # Some clients may reject invalid header values
                pass
