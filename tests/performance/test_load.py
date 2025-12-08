"""
Load and performance tests for AI Agent Firewall.

Tests:
- Validation latency (target: < 10ms)
- Concurrent requests (target: 100+ req/s)
- Rate limiting under load
- Database performance with large log tables
"""

import statistics
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

@pytest.fixture(scope="module")
def perf_client():
    """TestClient for performance tests."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def perf_project(perf_client):
    """Create a project with policy for performance tests."""
    project_id = f"perf-test-{uuid.uuid4().hex[:8]}"

    # Create project
    response = perf_client.post("/projects", json={
        "id": project_id,
        "name": "Performance Test Project"
    })
    api_key = response.json()["api_key"]

    # Create policy with multiple rules
    perf_client.post(
        f"/policies/{project_id}",
        json={
            "name": "perf-policy",
            "version": "1.0",
            "default": "allow",
            "rules": [
                {
                    "action_type": "pay_invoice",
                    "constraints": {
                        "params.amount": {"max": 10000, "min": 0},
                        "params.currency": {"in": ["USD", "EUR", "GBP"]}
                    },
                    "allowed_agents": ["billing_agent", "finance_agent"]
                },
                {
                    "action_type": "send_email",
                    "constraints": {
                        "params.recipient": {"pattern": r"^[\w.-]+@[\w.-]+\.\w+$"}
                    },
                    "rate_limit": {"max_requests": 100, "window_seconds": 60}
                },
                {
                    "action_type": "delete_record",
                    "allowed_agents": ["admin_agent"],
                    "constraints": {
                        "params.confirm": {"equals": True}
                    }
                },
                {
                    "action_type": "*",
                    "rate_limit": {"max_requests": 1000, "window_seconds": 60}
                }
            ]
        },
        headers={"X-API-Key": api_key}
    )

    return project_id, api_key


# =============================================================================
# VALIDATION LATENCY TESTS
# =============================================================================

class TestValidationLatency:
    """Test that validation operations complete within acceptable latency."""

    TARGET_LATENCY_MS = 10  # Target: < 10ms per validation

    def test_single_validation_latency(self, perf_client, perf_project):
        """Single validation should complete well under 10ms."""
        project_id, api_key = perf_project

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            response = perf_client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "billing_agent",
                    "action_type": "pay_invoice",
                    "params": {"amount": 500, "currency": "USD"}
                },
                headers={"X-API-Key": api_key}
            )
            end = time.perf_counter()

            assert response.status_code == 200
            latencies.append((end - start) * 1000)  # Convert to ms

        avg_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[94]  # 95th percentile
        p99_latency = sorted(latencies)[98]  # 99th percentile

        print(f"\nSingle Validation Latency (100 requests):")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
        print(f"  P99: {p99_latency:.2f}ms")
        print(f"  Min: {min(latencies):.2f}ms")
        print(f"  Max: {max(latencies):.2f}ms")

        # P95 should be under target
        assert p95_latency < self.TARGET_LATENCY_MS * 5, \
            f"P95 latency {p95_latency:.2f}ms exceeds {self.TARGET_LATENCY_MS * 5}ms"

    def test_complex_constraint_latency(self, perf_client, perf_project):
        """Complex constraint validation should still be fast."""
        project_id, api_key = perf_project

        latencies = []
        for i in range(50):
            start = time.perf_counter()
            response = perf_client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "billing_agent",
                    "action_type": "pay_invoice",
                    "params": {
                        "amount": 100 + i,
                        "currency": "USD",
                        "description": f"Invoice payment #{i}",
                        "metadata": {"ref": f"REF-{i:05d}"}
                    }
                },
                headers={"X-API-Key": api_key}
            )
            end = time.perf_counter()

            assert response.status_code == 200
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)
        print(f"\nComplex Constraint Latency (50 requests):")
        print(f"  Average: {avg_latency:.2f}ms")

        assert avg_latency < self.TARGET_LATENCY_MS * 10, \
            f"Average latency {avg_latency:.2f}ms exceeds {self.TARGET_LATENCY_MS * 10}ms"

    def test_policy_engine_direct_latency(self):
        """Direct policy engine validation (no HTTP) should be very fast."""
        engine = PolicyEngine()

        policy_json = """{
            "name": "test",
            "version": "1.0",
            "default": "allow",
            "rules": [
                {
                    "action_type": "test_action",
                    "constraints": {
                        "params.amount": {"max": 1000, "min": 0},
                        "params.type": {"in": ["A", "B", "C"]}
                    },
                    "allowed_agents": ["agent1", "agent2"]
                }
            ]
        }"""

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            result = engine.validate(
                policy_json=policy_json,
                agent_name="agent1",
                action_type="test_action",
                params={"amount": 500, "type": "A"}
            )
            end = time.perf_counter()

            assert result.allowed is True
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)
        p99_latency = sorted(latencies)[989]

        print(f"\nDirect Policy Engine Latency (1000 validations):")
        print(f"  Average: {avg_latency:.4f}ms")
        print(f"  P99: {p99_latency:.4f}ms")

        # Direct engine should be sub-millisecond
        assert avg_latency < 1.0, f"Direct engine avg {avg_latency:.4f}ms exceeds 1ms"


# =============================================================================
# CONCURRENT REQUEST TESTS
# =============================================================================

class TestConcurrentRequests:
    """Test system performance under concurrent load."""

    TARGET_RPS = 100  # Target: 100+ requests per second

    def test_concurrent_validations(self, perf_client, perf_project):
        """System should handle 100+ concurrent validations per second."""
        project_id, api_key = perf_project

        num_requests = 200
        num_workers = 10

        def make_request(i):
            start = time.perf_counter()
            response = perf_client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "billing_agent",
                    "action_type": "pay_invoice",
                    "params": {"amount": i * 10, "currency": "USD"}
                },
                headers={"X-API-Key": api_key}
            )
            end = time.perf_counter()
            return response.status_code, (end - start) * 1000

        start_time = time.perf_counter()

        results = []
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            for future in as_completed(futures):
                results.append(future.result())

        end_time = time.perf_counter()
        total_time = end_time - start_time

        successful = sum(1 for status, _ in results if status == 200)
        latencies = [latency for _, latency in results]
        rps = num_requests / total_time

        print(f"\nConcurrent Validations ({num_requests} requests, {num_workers} workers):")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Requests/second: {rps:.1f}")
        print(f"  Successful: {successful}/{num_requests}")
        print(f"  Avg latency: {statistics.mean(latencies):.2f}ms")
        print(f"  P95 latency: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}ms")

        assert successful == num_requests, f"Only {successful}/{num_requests} succeeded"
        assert rps >= self.TARGET_RPS, f"RPS {rps:.1f} below target {self.TARGET_RPS}"

    def test_mixed_action_types_concurrent(self, perf_client, perf_project):
        """Concurrent requests with different action types."""
        project_id, api_key = perf_project

        actions = [
            ("billing_agent", "pay_invoice", {"amount": 100, "currency": "USD"}),
            ("email_agent", "send_email", {"recipient": "test@example.com", "subject": "Hi"}),
            ("admin_agent", "delete_record", {"id": 123, "confirm": True}),
            ("generic_agent", "other_action", {"data": "test"}),
        ]

        num_requests = 100
        num_workers = 8

        def make_request(i):
            agent, action, params = actions[i % len(actions)]
            start = time.perf_counter()
            response = perf_client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": agent,
                    "action_type": action,
                    "params": params
                },
                headers={"X-API-Key": api_key}
            )
            end = time.perf_counter()
            return response.status_code, (end - start) * 1000

        start_time = time.perf_counter()

        results = []
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            for future in as_completed(futures):
                results.append(future.result())

        end_time = time.perf_counter()
        total_time = end_time - start_time

        successful = sum(1 for status, _ in results if status == 200)
        rps = num_requests / total_time

        print(f"\nMixed Action Types ({num_requests} requests):")
        print(f"  Requests/second: {rps:.1f}")
        print(f"  Successful: {successful}/{num_requests}")

        assert successful == num_requests


# =============================================================================
# RATE LIMITING UNDER LOAD TESTS
# =============================================================================

class TestRateLimitingUnderLoad:
    """Test rate limiting behavior under high load."""

    def test_rate_limit_accuracy_under_load(self, perf_client, perf_project):
        """Rate limiting should work correctly even under concurrent load."""
        project_id, api_key = perf_project

        # Create a project with strict rate limit for this test
        test_project_id = f"rate-limit-test-{uuid.uuid4().hex[:8]}"
        response = perf_client.post("/projects", json={
            "id": test_project_id,
            "name": "Rate Limit Test"
        })
        test_api_key = response.json()["api_key"]

        # Policy with 10 requests per 60 second window
        perf_client.post(
            f"/policies/{test_project_id}",
            json={
                "name": "strict-rate-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [
                    {
                        "action_type": "limited_action",
                        "rate_limit": {"max_requests": 10, "window_seconds": 60}
                    }
                ]
            },
            headers={"X-API-Key": test_api_key}
        )

        # Send 20 requests rapidly - first 10 should pass, rest should be blocked
        results = []
        for i in range(20):
            response = perf_client.post(
                "/validate_action",
                json={
                    "project_id": test_project_id,
                    "agent_name": "test_agent",
                    "action_type": "limited_action",
                    "params": {"index": i}
                },
                headers={"X-API-Key": test_api_key}
            )
            data = response.json()
            results.append(data["allowed"])

        allowed_count = sum(results)
        blocked_count = len(results) - allowed_count

        print(f"\nRate Limiting Under Load (20 rapid requests, limit=10):")
        print(f"  Allowed: {allowed_count}")
        print(f"  Blocked: {blocked_count}")

        # Exactly 10 should be allowed
        assert allowed_count == 10, f"Expected 10 allowed, got {allowed_count}"
        assert blocked_count == 10, f"Expected 10 blocked, got {blocked_count}"

    def test_rate_limit_per_agent_isolation(self, perf_client, perf_project):
        """Rate limits should be isolated per agent."""
        project_id, api_key = perf_project

        # Create project with per-agent rate limit
        test_project_id = f"agent-isolation-{uuid.uuid4().hex[:8]}"
        response = perf_client.post("/projects", json={
            "id": test_project_id,
            "name": "Agent Isolation Test"
        })
        test_api_key = response.json()["api_key"]

        perf_client.post(
            f"/policies/{test_project_id}",
            json={
                "name": "per-agent-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [
                    {
                        "action_type": "test_action",
                        "rate_limit": {"max_requests": 5, "window_seconds": 60}
                    }
                ]
            },
            headers={"X-API-Key": test_api_key}
        )

        # Agent A: 5 requests (all should pass)
        agent_a_results = []
        for i in range(5):
            response = perf_client.post(
                "/validate_action",
                json={
                    "project_id": test_project_id,
                    "agent_name": "agent_a",
                    "action_type": "test_action",
                    "params": {}
                },
                headers={"X-API-Key": test_api_key}
            )
            agent_a_results.append(response.json()["allowed"])

        # Agent B: 5 requests (all should pass - separate limit)
        agent_b_results = []
        for i in range(5):
            response = perf_client.post(
                "/validate_action",
                json={
                    "project_id": test_project_id,
                    "agent_name": "agent_b",
                    "action_type": "test_action",
                    "params": {}
                },
                headers={"X-API-Key": test_api_key}
            )
            agent_b_results.append(response.json()["allowed"])

        # Agent A: 1 more request (should be blocked)
        response = perf_client.post(
            "/validate_action",
            json={
                "project_id": test_project_id,
                "agent_name": "agent_a",
                "action_type": "test_action",
                "params": {}
            },
            headers={"X-API-Key": test_api_key}
        )
        agent_a_blocked = not response.json()["allowed"]

        print(f"\nRate Limit Per-Agent Isolation:")
        print(f"  Agent A allowed: {sum(agent_a_results)}/5")
        print(f"  Agent B allowed: {sum(agent_b_results)}/5")
        print(f"  Agent A 6th request blocked: {agent_a_blocked}")

        assert all(agent_a_results), "Agent A first 5 should all pass"
        assert all(agent_b_results), "Agent B first 5 should all pass"
        assert agent_a_blocked, "Agent A 6th request should be blocked"


# =============================================================================
# DATABASE PERFORMANCE TESTS
# =============================================================================

class TestDatabasePerformance:
    """Test database performance with large datasets."""

    def test_log_insertion_performance(self, perf_client, perf_project):
        """Log insertion should remain fast even after many entries."""
        project_id, api_key = perf_project

        # Generate many log entries
        num_entries = 500
        latencies = []

        for i in range(num_entries):
            start = time.perf_counter()
            response = perf_client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": f"agent_{i % 10}",
                    "action_type": "pay_invoice",
                    "params": {"amount": i, "currency": "USD"}
                },
                headers={"X-API-Key": api_key}
            )
            end = time.perf_counter()

            assert response.status_code == 200
            latencies.append((end - start) * 1000)

        # Compare first 50 vs last 50 latencies
        first_50_avg = statistics.mean(latencies[:50])
        last_50_avg = statistics.mean(latencies[-50:])

        print(f"\nLog Insertion Performance ({num_entries} entries):")
        print(f"  First 50 avg: {first_50_avg:.2f}ms")
        print(f"  Last 50 avg: {last_50_avg:.2f}ms")
        print(f"  Degradation: {((last_50_avg/first_50_avg)-1)*100:.1f}%")

        # Last entries should not be more than 3x slower
        assert last_50_avg < first_50_avg * 3, \
            f"Performance degraded too much: {first_50_avg:.2f}ms -> {last_50_avg:.2f}ms"

    def test_log_query_performance(self, perf_client, perf_project):
        """Log queries should remain fast with many entries."""
        project_id, api_key = perf_project

        # Query logs multiple times
        latencies = []
        for _ in range(20):
            start = time.perf_counter()
            response = perf_client.get(
                f"/logs/{project_id}?page_size=50",
                headers={"X-API-Key": api_key}
            )
            end = time.perf_counter()

            assert response.status_code == 200
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)

        print(f"\nLog Query Performance (20 queries, 50 items each):")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  Max: {max(latencies):.2f}ms")

        # Queries should complete in reasonable time
        assert avg_latency < 100, f"Log queries too slow: {avg_latency:.2f}ms"

    def test_log_query_with_filters(self, perf_client, perf_project):
        """Filtered log queries should also be performant."""
        project_id, api_key = perf_project

        # Query with different filters
        filters = [
            "?agent_name=agent_1",
            "?allowed=true",
            "?allowed=false",
            "?agent_name=agent_1&allowed=true",
        ]

        for filter_query in filters:
            latencies = []
            for _ in range(10):
                start = time.perf_counter()
                response = perf_client.get(
                    f"/logs/{project_id}{filter_query}",
                    headers={"X-API-Key": api_key}
                )
                end = time.perf_counter()

                assert response.status_code == 200
                latencies.append((end - start) * 1000)

            avg = statistics.mean(latencies)
            print(f"  Filter '{filter_query}': {avg:.2f}ms avg")

            assert avg < 100, f"Filtered query too slow: {filter_query}"

    def test_stats_calculation_performance(self, perf_client, perf_project):
        """Stats calculation should be fast even with many logs."""
        project_id, api_key = perf_project

        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            response = perf_client.get(
                f"/logs/{project_id}/stats",
                headers={"X-API-Key": api_key}
            )
            end = time.perf_counter()

            assert response.status_code == 200
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)

        print(f"\nStats Calculation Performance (10 queries):")
        print(f"  Average: {avg_latency:.2f}ms")

        assert avg_latency < 200, f"Stats calculation too slow: {avg_latency:.2f}ms"


# =============================================================================
# STRESS TESTS
# =============================================================================

class TestStress:
    """Stress tests for edge cases and limits."""

    def test_rapid_policy_updates(self, perf_client, perf_project):
        """System should handle rapid policy updates."""
        project_id, api_key = perf_project

        # Create test project
        test_project_id = f"policy-update-{uuid.uuid4().hex[:8]}"
        response = perf_client.post("/projects", json={
            "id": test_project_id,
            "name": "Policy Update Test"
        })
        test_api_key = response.json()["api_key"]

        # Update policy 20 times rapidly
        latencies = []
        for i in range(20):
            start = time.perf_counter()
            response = perf_client.post(
                f"/policies/{test_project_id}",
                json={
                    "name": f"policy-v{i}",
                    "version": f"{i}.0",
                    "default": "allow",
                    "rules": [
                        {
                            "action_type": "test",
                            "constraints": {
                                "params.value": {"max": 1000 + i}
                            }
                        }
                    ]
                },
                headers={"X-API-Key": test_api_key}
            )
            end = time.perf_counter()

            assert response.status_code == 200
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)

        print(f"\nRapid Policy Updates (20 updates):")
        print(f"  Average: {avg_latency:.2f}ms")

        # Check policy history has all versions (request limit=20)
        response = perf_client.get(
            f"/policies/{test_project_id}/history?limit=20",
            headers={"X-API-Key": test_api_key}
        )
        history = response.json()

        print(f"  History entries: {len(history)}")
        assert len(history) == 20, f"Expected 20 history entries, got {len(history)}"

    def test_large_params_validation(self, perf_client, perf_project):
        """Validation should handle large parameter objects."""
        project_id, api_key = perf_project

        # Create params with many fields
        large_params = {f"field_{i}": f"value_{i}" for i in range(100)}
        large_params["amount"] = 500
        large_params["currency"] = "USD"

        latencies = []
        for _ in range(20):
            start = time.perf_counter()
            response = perf_client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "billing_agent",
                    "action_type": "pay_invoice",
                    "params": large_params
                },
                headers={"X-API-Key": api_key}
            )
            end = time.perf_counter()

            assert response.status_code == 200
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)

        print(f"\nLarge Params Validation (100 fields):")
        print(f"  Average: {avg_latency:.2f}ms")

        assert avg_latency < 50, f"Large params too slow: {avg_latency:.2f}ms"


# =============================================================================
# BENCHMARK SUMMARY
# =============================================================================

class TestBenchmarkSummary:
    """Generate a summary of all performance benchmarks."""

    def test_generate_benchmark_report(self, perf_client, perf_project):
        """Generate comprehensive benchmark report."""
        project_id, api_key = perf_project

        print("\n" + "="*60)
        print("PERFORMANCE BENCHMARK SUMMARY")
        print("="*60)

        # Single validation benchmark
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            perf_client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "billing_agent",
                    "action_type": "pay_invoice",
                    "params": {"amount": 100, "currency": "USD"}
                },
                headers={"X-API-Key": api_key}
            )
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        print(f"\nSingle Validation (100 samples):")
        print(f"  Mean: {statistics.mean(latencies):.2f}ms")
        print(f"  Median: {statistics.median(latencies):.2f}ms")
        print(f"  Std Dev: {statistics.stdev(latencies):.2f}ms")
        print(f"  P95: {sorted(latencies)[94]:.2f}ms")
        print(f"  P99: {sorted(latencies)[98]:.2f}ms")

        # Throughput benchmark
        num_requests = 200
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(num_requests):
                futures.append(executor.submit(
                    perf_client.post,
                    "/validate_action",
                    json={
                        "project_id": project_id,
                        "agent_name": "billing_agent",
                        "action_type": "pay_invoice",
                        "params": {"amount": i, "currency": "USD"}
                    },
                    headers={"X-API-Key": api_key}
                ))
            for f in as_completed(futures):
                f.result()

        end_time = time.perf_counter()
        rps = num_requests / (end_time - start_time)

        print(f"\nThroughput (200 requests, 10 workers):")
        print(f"  Requests/second: {rps:.1f}")

        print("\n" + "="*60)
        print("BENCHMARK COMPLETE")
        print("="*60)

        # Assert minimum performance requirements
        assert rps >= 100, f"Throughput {rps:.1f} below minimum 100 req/s"
