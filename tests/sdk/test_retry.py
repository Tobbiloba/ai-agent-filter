"""
SDK Retry Logic Tests for AI Agent Firewall Python SDK.

Tests:
- Exponential backoff calculation
- Retry on network errors
- Retry on server errors (5xx)
- Retry on rate limit (429)
- No retry on client errors (4xx except 429)
- Max retries limit
- Retry configuration options
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
import httpx

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sdk" / "python"))

from ai_firewall import AIFirewall
from ai_firewall.exceptions import (
    AIFirewallError,
    AuthenticationError,
    NetworkError,
    ValidationError,
    RateLimitError,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_response():
    """Create a mock httpx.Response."""
    def _create(status_code: int, json_data: dict = None, text: str = ""):
        response = Mock(spec=httpx.Response)
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.text = text
        return response
    return _create


@pytest.fixture
def valid_validation_response():
    """Valid response for /validate_action endpoint."""
    return {
        "allowed": True,
        "action_id": "act_123456",
        "timestamp": "2025-01-01T12:00:00Z",
        "reason": None,
        "execution_time_ms": 5,
        "simulated": False,
    }


# =============================================================================
# EXPONENTIAL BACKOFF TESTS
# =============================================================================

class TestExponentialBackoff:
    """Tests for exponential backoff calculation."""

    def test_backoff_increases_exponentially(self):
        """Backoff delay should increase exponentially."""
        client = AIFirewall(
            api_key="af_test",
            project_id="proj",
            retry_base_delay=1.0,
            retry_max_delay=30.0,
        )

        # Get delays for first few attempts (without jitter for testing)
        with patch('random.random', return_value=0.5):  # 0 jitter
            delay_0 = client._calculate_backoff(0)  # 1 * 2^0 = 1
            delay_1 = client._calculate_backoff(1)  # 1 * 2^1 = 2
            delay_2 = client._calculate_backoff(2)  # 1 * 2^2 = 4
            delay_3 = client._calculate_backoff(3)  # 1 * 2^3 = 8

        assert delay_0 == pytest.approx(1.0, rel=0.01)
        assert delay_1 == pytest.approx(2.0, rel=0.01)
        assert delay_2 == pytest.approx(4.0, rel=0.01)
        assert delay_3 == pytest.approx(8.0, rel=0.01)

        client.close()

    def test_backoff_respects_max_delay(self):
        """Backoff should be capped at max_delay."""
        client = AIFirewall(
            api_key="af_test",
            project_id="proj",
            retry_base_delay=1.0,
            retry_max_delay=5.0,
        )

        with patch('random.random', return_value=0.5):  # 0 jitter
            delay = client._calculate_backoff(10)  # Would be 1024 without cap

        assert delay == pytest.approx(5.0, rel=0.01)
        client.close()

    def test_backoff_includes_jitter(self):
        """Backoff should include jitter (±25%)."""
        client = AIFirewall(
            api_key="af_test",
            project_id="proj",
            retry_base_delay=4.0,
            retry_max_delay=30.0,
        )

        # Test with different random values
        delays = []
        for random_val in [0.0, 0.5, 1.0]:
            with patch('random.random', return_value=random_val):
                delays.append(client._calculate_backoff(0))

        # Base delay is 4.0, jitter is ±25% (±1.0)
        # So delays should be in range [3.0, 5.0]
        assert min(delays) >= 3.0
        assert max(delays) <= 5.0
        # Should have some variation
        assert len(set(delays)) > 1

        client.close()


# =============================================================================
# RETRY ON NETWORK ERRORS TESTS
# =============================================================================

class TestRetryOnNetworkErrors:
    """Tests for retry behavior on network errors."""

    def test_retry_on_connection_error(self, mock_response, valid_validation_response):
        """Should retry on connection errors."""
        with patch.object(httpx.Client, 'request') as mock_request:
            # Fail twice, then succeed
            mock_request.side_effect = [
                httpx.ConnectError("Connection refused"),
                httpx.ConnectError("Connection refused"),
                mock_response(200, valid_validation_response),
            ]

            with patch('time.sleep'):  # Skip actual sleep
                client = AIFirewall(
                    api_key="af_test",
                    project_id="proj",
                    max_retries=3,
                )
                result = client.execute("agent", "action", {})

            assert result.allowed is True
            assert mock_request.call_count == 3
            client.close()

    def test_retry_on_timeout(self, mock_response, valid_validation_response):
        """Should retry on timeout errors."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = [
                httpx.TimeoutException("Timeout"),
                mock_response(200, valid_validation_response),
            ]

            with patch('time.sleep'):
                client = AIFirewall(
                    api_key="af_test",
                    project_id="proj",
                    max_retries=3,
                )
                result = client.execute("agent", "action", {})

            assert result.allowed is True
            assert mock_request.call_count == 2
            client.close()

    def test_no_retry_when_disabled(self):
        """Should not retry network errors when retry_on_network_error=False."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection refused")

            client = AIFirewall(
                api_key="af_test",
                project_id="proj",
                max_retries=3,
                retry_on_network_error=False,
            )

            with pytest.raises(NetworkError):
                client.execute("agent", "action", {})

            # Should only try once
            assert mock_request.call_count == 1
            client.close()

    def test_max_retries_exceeded_network_error(self):
        """Should raise after max retries on network error."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection refused")

            with patch('time.sleep'):
                client = AIFirewall(
                    api_key="af_test",
                    project_id="proj",
                    max_retries=2,
                )

                with pytest.raises(NetworkError) as exc_info:
                    client.execute("agent", "action", {})

                assert "3 attempts" in str(exc_info.value)  # 1 initial + 2 retries

            # 3 total attempts (initial + 2 retries)
            assert mock_request.call_count == 3
            client.close()


# =============================================================================
# RETRY ON SERVER ERRORS TESTS
# =============================================================================

class TestRetryOnServerErrors:
    """Tests for retry behavior on server errors (5xx)."""

    def test_retry_on_500(self, mock_response, valid_validation_response):
        """Should retry on 500 Internal Server Error."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = [
                mock_response(500, {}, "Internal Server Error"),
                mock_response(200, valid_validation_response),
            ]

            with patch('time.sleep'):
                client = AIFirewall(api_key="af_test", project_id="proj")
                result = client.execute("agent", "action", {})

            assert result.allowed is True
            assert mock_request.call_count == 2
            client.close()

    def test_retry_on_502(self, mock_response, valid_validation_response):
        """Should retry on 502 Bad Gateway."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = [
                mock_response(502, {}, "Bad Gateway"),
                mock_response(200, valid_validation_response),
            ]

            with patch('time.sleep'):
                client = AIFirewall(api_key="af_test", project_id="proj")
                result = client.execute("agent", "action", {})

            assert result.allowed is True
            assert mock_request.call_count == 2
            client.close()

    def test_retry_on_503(self, mock_response, valid_validation_response):
        """Should retry on 503 Service Unavailable."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = [
                mock_response(503, {}, "Service Unavailable"),
                mock_response(200, valid_validation_response),
            ]

            with patch('time.sleep'):
                client = AIFirewall(api_key="af_test", project_id="proj")
                result = client.execute("agent", "action", {})

            assert result.allowed is True
            assert mock_request.call_count == 2
            client.close()

    def test_retry_on_504(self, mock_response, valid_validation_response):
        """Should retry on 504 Gateway Timeout."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = [
                mock_response(504, {}, "Gateway Timeout"),
                mock_response(200, valid_validation_response),
            ]

            with patch('time.sleep'):
                client = AIFirewall(api_key="af_test", project_id="proj")
                result = client.execute("agent", "action", {})

            assert result.allowed is True
            assert mock_request.call_count == 2
            client.close()

    def test_max_retries_exceeded_server_error(self, mock_response):
        """Should raise after max retries on server error."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(500, {}, "Internal Server Error")

            with patch('time.sleep'):
                client = AIFirewall(
                    api_key="af_test",
                    project_id="proj",
                    max_retries=2,
                )

                with pytest.raises(AIFirewallError) as exc_info:
                    client.execute("agent", "action", {})

                assert "500" in str(exc_info.value)

            # 3 total attempts
            assert mock_request.call_count == 3
            client.close()


# =============================================================================
# RETRY ON RATE LIMIT TESTS
# =============================================================================

class TestRetryOnRateLimit:
    """Tests for retry behavior on rate limit (429)."""

    def test_retry_on_429(self, mock_response, valid_validation_response):
        """Should retry on 429 Too Many Requests."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = [
                mock_response(429, {}, "Too Many Requests"),
                mock_response(200, valid_validation_response),
            ]

            with patch('time.sleep'):
                client = AIFirewall(api_key="af_test", project_id="proj")
                result = client.execute("agent", "action", {})

            assert result.allowed is True
            assert mock_request.call_count == 2
            client.close()

    def test_max_retries_exceeded_rate_limit(self, mock_response):
        """Should raise RateLimitError after max retries on 429."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(429, {}, "Too Many Requests")

            with patch('time.sleep'):
                client = AIFirewall(
                    api_key="af_test",
                    project_id="proj",
                    max_retries=2,
                )

                with pytest.raises(RateLimitError):
                    client.execute("agent", "action", {})

            assert mock_request.call_count == 3
            client.close()


# =============================================================================
# NO RETRY ON CLIENT ERRORS TESTS
# =============================================================================

class TestNoRetryOnClientErrors:
    """Tests that client errors are NOT retried."""

    def test_no_retry_on_401(self, mock_response):
        """Should NOT retry on 401 Unauthorized."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(401, {"detail": "Invalid key"})

            client = AIFirewall(api_key="af_invalid", project_id="proj")

            with pytest.raises(AuthenticationError):
                client.execute("agent", "action", {})

            # Should only try once (no retries)
            assert mock_request.call_count == 1
            client.close()

    def test_no_retry_on_403(self, mock_response):
        """Should NOT retry on 403 Forbidden."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(403, {"detail": "Access denied"})

            client = AIFirewall(api_key="af_wrong", project_id="proj")

            with pytest.raises(AuthenticationError):
                client.execute("agent", "action", {})

            assert mock_request.call_count == 1
            client.close()

    def test_no_retry_on_404(self, mock_response):
        """Should NOT retry on 404 Not Found."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(404, {"detail": "Not found"})

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(AIFirewallError):
                client.execute("agent", "action", {})

            assert mock_request.call_count == 1
            client.close()

    def test_no_retry_on_422(self, mock_response):
        """Should NOT retry on 422 Validation Error."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(422, {"detail": "Invalid data"})

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(ValidationError):
                client.execute("agent", "action", {})

            assert mock_request.call_count == 1
            client.close()


# =============================================================================
# RETRY CONFIGURATION TESTS
# =============================================================================

class TestRetryConfiguration:
    """Tests for retry configuration options."""

    def test_zero_retries_disables_retry(self, mock_response):
        """Setting max_retries=0 should disable retries."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(500, {}, "Error")

            client = AIFirewall(
                api_key="af_test",
                project_id="proj",
                max_retries=0,
            )

            with pytest.raises(AIFirewallError):
                client.execute("agent", "action", {})

            # Should only try once
            assert mock_request.call_count == 1
            client.close()

    def test_custom_retry_status_codes(self, mock_response, valid_validation_response):
        """Custom retry_on_status should be respected."""
        with patch.object(httpx.Client, 'request') as mock_request:
            # 418 is not in default retry codes, but we add it
            mock_request.side_effect = [
                mock_response(418, {}, "I'm a teapot"),
                mock_response(200, valid_validation_response),
            ]

            with patch('time.sleep'):
                client = AIFirewall(
                    api_key="af_test",
                    project_id="proj",
                    retry_on_status={418},  # Custom retry code
                )
                result = client.execute("agent", "action", {})

            assert result.allowed is True
            assert mock_request.call_count == 2
            client.close()

    def test_default_retry_status_codes(self):
        """Default retry status codes should be 429, 500, 502, 503, 504."""
        assert AIFirewall.DEFAULT_RETRY_STATUS_CODES == frozenset({429, 500, 502, 503, 504})

    def test_default_max_retries(self):
        """Default max_retries should be 3."""
        assert AIFirewall.DEFAULT_MAX_RETRIES == 3

    def test_default_base_delay(self):
        """Default retry_base_delay should be 1.0 second."""
        assert AIFirewall.DEFAULT_RETRY_BASE_DELAY == 1.0

    def test_default_max_delay(self):
        """Default retry_max_delay should be 30.0 seconds."""
        assert AIFirewall.DEFAULT_RETRY_MAX_DELAY == 30.0


# =============================================================================
# SLEEP TIMING TESTS
# =============================================================================

class TestSleepTiming:
    """Tests that sleep is called with correct delays."""

    def test_sleep_called_between_retries(self, mock_response, valid_validation_response):
        """Sleep should be called between retry attempts."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = [
                mock_response(503, {}, "Service Unavailable"),
                mock_response(503, {}, "Service Unavailable"),
                mock_response(200, valid_validation_response),
            ]

            with patch('time.sleep') as mock_sleep:
                with patch('random.random', return_value=0.5):  # 0 jitter
                    client = AIFirewall(
                        api_key="af_test",
                        project_id="proj",
                        retry_base_delay=1.0,
                    )
                    client.execute("agent", "action", {})

                # Should have slept twice (after 1st and 2nd failures)
                assert mock_sleep.call_count == 2
                # First sleep: ~1.0s, Second sleep: ~2.0s
                calls = mock_sleep.call_args_list
                assert calls[0][0][0] == pytest.approx(1.0, rel=0.01)
                assert calls[1][0][0] == pytest.approx(2.0, rel=0.01)

            client.close()

    def test_no_sleep_on_success(self, mock_response, valid_validation_response):
        """Sleep should not be called when request succeeds immediately."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, valid_validation_response)

            with patch('time.sleep') as mock_sleep:
                client = AIFirewall(api_key="af_test", project_id="proj")
                client.execute("agent", "action", {})

            mock_sleep.assert_not_called()
            client.close()
