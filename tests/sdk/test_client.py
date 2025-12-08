"""
SDK Client Tests for AI Agent Firewall Python SDK.

Tests:
- SDK initialization
- Network error handling
- Timeout handling
- Exception types
- Response handling
- Retry behavior (documenting current behavior)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
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
    PolicyNotFoundError,
    ProjectNotFoundError,
    ActionBlockedError,
    RateLimitError,
)
from ai_firewall.models import ValidationResult, Policy, LogsPage, AuditLogEntry


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
        "execution_time_ms": 5
    }


@pytest.fixture
def blocked_validation_response():
    """Blocked action response."""
    return {
        "allowed": False,
        "action_id": "act_789012",
        "timestamp": "2025-01-01T12:00:00Z",
        "reason": "Amount exceeds maximum limit",
        "execution_time_ms": 3
    }


@pytest.fixture
def valid_policy_response():
    """Valid response for /policies endpoint."""
    return {
        "id": 1,
        "project_id": "test-project",
        "name": "test-policy",
        "version": "1.0",
        "rules": {"default": "allow", "rules": []},
        "is_active": True,
        "created_at": "2025-01-01T10:00:00Z",
        "updated_at": "2025-01-01T10:00:00Z"
    }


@pytest.fixture
def valid_logs_response():
    """Valid response for /logs endpoint."""
    return {
        "items": [
            {
                "action_id": "act_001",
                "project_id": "test-project",
                "agent_name": "test-agent",
                "action_type": "test-action",
                "params": {"key": "value"},
                "allowed": True,
                "reason": None,
                "policy_version": "1.0",
                "execution_time_ms": 5,
                "timestamp": "2025-01-01T11:00:00Z"
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 50,
        "has_more": False
    }


# =============================================================================
# SDK INITIALIZATION TESTS
# =============================================================================

class TestSDKInitialization:
    """Tests for AIFirewall client initialization."""

    def test_init_with_required_params(self):
        """Client initializes with only required params."""
        client = AIFirewall(
            api_key="af_test123",
            project_id="my-project"
        )

        assert client.api_key == "af_test123"
        assert client.project_id == "my-project"
        assert client.base_url == "http://localhost:8000"
        assert client.timeout == 30.0
        assert client.strict is False

        client.close()

    def test_init_with_custom_base_url(self):
        """Client accepts custom base URL."""
        client = AIFirewall(
            api_key="af_test123",
            project_id="my-project",
            base_url="https://api.example.com"
        )

        assert client.base_url == "https://api.example.com"
        client.close()

    def test_init_strips_trailing_slash_from_base_url(self):
        """Base URL trailing slash is stripped."""
        client = AIFirewall(
            api_key="af_test123",
            project_id="my-project",
            base_url="https://api.example.com/"
        )

        assert client.base_url == "https://api.example.com"
        client.close()

    def test_init_with_custom_timeout(self):
        """Client accepts custom timeout."""
        client = AIFirewall(
            api_key="af_test123",
            project_id="my-project",
            timeout=60.0
        )

        assert client.timeout == 60.0
        client.close()

    def test_init_with_strict_mode(self):
        """Client accepts strict mode flag."""
        client = AIFirewall(
            api_key="af_test123",
            project_id="my-project",
            strict=True
        )

        assert client.strict is True
        client.close()

    def test_init_sets_correct_headers(self):
        """Client sets correct HTTP headers."""
        client = AIFirewall(
            api_key="af_test123",
            project_id="my-project"
        )

        # Check the internal httpx client headers
        assert client._client.headers["X-API-Key"] == "af_test123"
        assert client._client.headers["Content-Type"] == "application/json"
        client.close()

    def test_context_manager_closes_client(self):
        """Context manager properly closes client."""
        with AIFirewall(api_key="af_test", project_id="proj") as client:
            assert client._client is not None

        # After context exit, client should be closed
        # (we can't easily test this without checking internal state)

    def test_default_timeout_is_30_seconds(self):
        """Default timeout should be 30 seconds."""
        assert AIFirewall.DEFAULT_TIMEOUT == 30.0

    def test_default_base_url_is_localhost(self):
        """Default base URL should be localhost:8000."""
        assert AIFirewall.DEFAULT_BASE_URL == "http://localhost:8000"


# =============================================================================
# NETWORK ERROR HANDLING TESTS
# =============================================================================

class TestNetworkErrorHandling:
    """Tests for network error handling."""

    def test_connection_refused_raises_network_error(self):
        """Connection refused raises NetworkError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection refused")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(NetworkError) as exc_info:
                client.execute("agent", "action", {})

            assert "Network error" in str(exc_info.value)
            client.close()

    def test_dns_resolution_error_raises_network_error(self):
        """DNS resolution failure raises NetworkError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.ConnectError("Name or service not known")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(NetworkError):
                client.execute("agent", "action", {})

            client.close()

    def test_connection_timeout_raises_network_error(self):
        """Connection timeout raises NetworkError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.ConnectTimeout("Connection timed out")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(NetworkError):
                client.execute("agent", "action", {})

            client.close()

    def test_read_timeout_raises_network_error(self):
        """Read timeout raises NetworkError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.ReadTimeout("Read timed out")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(NetworkError):
                client.execute("agent", "action", {})

            client.close()

    def test_network_error_contains_original_message(self):
        """NetworkError preserves original error message."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.ConnectError("Custom error message")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(NetworkError) as exc_info:
                client.execute("agent", "action", {})

            assert "Custom error message" in str(exc_info.value)
            client.close()

    def test_network_error_inherits_from_base_exception(self):
        """NetworkError inherits from AIFirewallError."""
        assert issubclass(NetworkError, AIFirewallError)

        error = NetworkError("test")
        assert isinstance(error, AIFirewallError)


# =============================================================================
# TIMEOUT HANDLING TESTS
# =============================================================================

class TestTimeoutHandling:
    """Tests for timeout configuration and handling."""

    def test_timeout_passed_to_httpx_client(self):
        """Custom timeout is passed to httpx client."""
        with patch('ai_firewall.client.httpx.Client') as mock_client_class:
            mock_instance = MagicMock()
            mock_client_class.return_value = mock_instance

            client = AIFirewall(
                api_key="af_test",
                project_id="proj",
                timeout=45.0
            )

            # Verify httpx.Client was called with the timeout
            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs['timeout'] == 45.0

    def test_default_timeout_passed_when_not_specified(self):
        """Default timeout (30s) is used when not specified."""
        with patch('ai_firewall.client.httpx.Client') as mock_client_class:
            mock_instance = MagicMock()
            mock_client_class.return_value = mock_instance

            client = AIFirewall(
                api_key="af_test",
                project_id="proj"
            )

            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs['timeout'] == 30.0

    def test_timeout_exception_wrapped_as_network_error(self):
        """Timeout exceptions are wrapped as NetworkError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Request timed out")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(NetworkError):
                client.execute("agent", "action", {})

            client.close()

    def test_write_timeout_raises_network_error(self):
        """Write timeout raises NetworkError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.WriteTimeout("Write timed out")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(NetworkError):
                client.execute("agent", "action", {})

            client.close()


# =============================================================================
# EXCEPTION TYPES TESTS
# =============================================================================

class TestExceptionTypes:
    """Tests for exception type handling based on HTTP status codes."""

    def test_401_raises_authentication_error(self, mock_response):
        """401 response raises AuthenticationError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(401, {"detail": "Invalid key"})

            client = AIFirewall(api_key="af_invalid", project_id="proj")

            with pytest.raises(AuthenticationError) as exc_info:
                client.execute("agent", "action", {})

            assert "invalid" in str(exc_info.value).lower()
            client.close()

    def test_403_raises_authentication_error(self, mock_response):
        """403 response raises AuthenticationError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(403, {"detail": "Access denied"})

            client = AIFirewall(api_key="af_wrong", project_id="proj")

            with pytest.raises(AuthenticationError) as exc_info:
                client.execute("agent", "action", {})

            assert "access" in str(exc_info.value).lower()
            client.close()

    def test_404_with_policy_raises_policy_not_found_error(self, mock_response):
        """404 with 'policy' in message raises PolicyNotFoundError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(404, {"detail": "No active policy found"})

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(PolicyNotFoundError):
                client.get_policy()

            client.close()

    def test_404_with_project_raises_project_not_found_error(self, mock_response):
        """404 with 'project' in message raises ProjectNotFoundError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(404, {"detail": "Project not found"})

            client = AIFirewall(api_key="af_test", project_id="nonexistent")

            with pytest.raises(ProjectNotFoundError):
                client.get_policy()

            client.close()

    def test_404_generic_raises_ai_firewall_error(self, mock_response):
        """404 without specific keyword raises generic AIFirewallError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(404, {"detail": "Resource not found"})

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(AIFirewallError):
                client.get_policy()

            client.close()

    def test_422_raises_validation_error(self, mock_response):
        """422 response raises ValidationError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(422, {"detail": "Missing field"})

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(ValidationError) as exc_info:
                client.execute("agent", "action", {})

            assert "Invalid request" in str(exc_info.value)
            client.close()

    def test_500_raises_ai_firewall_error(self, mock_response):
        """500 response raises generic AIFirewallError."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(500, {}, "Internal Server Error")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(AIFirewallError) as exc_info:
                client.execute("agent", "action", {})

            assert "500" in str(exc_info.value)
            client.close()

    def test_action_blocked_error_in_strict_mode(
        self, mock_response, blocked_validation_response
    ):
        """Blocked action raises ActionBlockedError in strict mode."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, blocked_validation_response)

            client = AIFirewall(api_key="af_test", project_id="proj", strict=True)

            with pytest.raises(ActionBlockedError) as exc_info:
                client.execute("agent", "action", {"amount": 10000})

            assert exc_info.value.reason == "Amount exceeds maximum limit"
            assert exc_info.value.action_id == "act_789012"
            client.close()

    def test_action_blocked_no_error_non_strict_mode(
        self, mock_response, blocked_validation_response
    ):
        """Blocked action returns result (no exception) in non-strict mode."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, blocked_validation_response)

            client = AIFirewall(api_key="af_test", project_id="proj", strict=False)

            result = client.execute("agent", "action", {"amount": 10000})

            assert result.allowed is False
            assert result.reason == "Amount exceeds maximum limit"
            client.close()

    def test_rate_limit_error_class_exists(self):
        """RateLimitError class exists and inherits from AIFirewallError."""
        assert issubclass(RateLimitError, AIFirewallError)

        error = RateLimitError("Rate limit exceeded")
        assert isinstance(error, AIFirewallError)

    def test_all_exceptions_inherit_from_base(self):
        """All SDK exceptions inherit from AIFirewallError."""
        exception_classes = [
            AuthenticationError,
            NetworkError,
            ValidationError,
            PolicyNotFoundError,
            ProjectNotFoundError,
            ActionBlockedError,
            RateLimitError,
        ]

        for exc_class in exception_classes:
            assert issubclass(exc_class, AIFirewallError), \
                f"{exc_class.__name__} should inherit from AIFirewallError"


# =============================================================================
# RESPONSE HANDLING TESTS
# =============================================================================

class TestResponseHandling:
    """Tests for response parsing and model creation."""

    def test_execute_returns_validation_result(
        self, mock_response, valid_validation_response
    ):
        """execute() returns ValidationResult model."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, valid_validation_response)

            client = AIFirewall(api_key="af_test", project_id="proj")
            result = client.execute("agent", "action", {"key": "value"})

            assert isinstance(result, ValidationResult)
            assert result.allowed is True
            assert result.action_id == "act_123456"
            assert isinstance(result.timestamp, datetime)
            client.close()

    def test_execute_sends_correct_payload(self, mock_response, valid_validation_response):
        """execute() sends correct JSON payload."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, valid_validation_response)

            client = AIFirewall(api_key="af_test", project_id="test-project")
            client.execute("my-agent", "my-action", {"param1": "value1"})

            # Verify the request was made with correct arguments
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0] == ("POST", "/validate_action")
            assert call_args[1]["json"] == {
                "project_id": "test-project",
                "agent_name": "my-agent",
                "action_type": "my-action",
                "params": {"param1": "value1"}
            }
            client.close()

    def test_execute_with_empty_params(self, mock_response, valid_validation_response):
        """execute() handles None params by sending empty dict."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, valid_validation_response)

            client = AIFirewall(api_key="af_test", project_id="proj")
            client.execute("agent", "action", None)

            call_args = mock_request.call_args
            assert call_args[1]["json"]["params"] == {}
            client.close()

    def test_get_policy_returns_policy_model(
        self, mock_response, valid_policy_response
    ):
        """get_policy() returns Policy model."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, valid_policy_response)

            client = AIFirewall(api_key="af_test", project_id="test-project")
            policy = client.get_policy()

            assert isinstance(policy, Policy)
            assert policy.id == 1
            assert policy.project_id == "test-project"
            assert policy.name == "test-policy"
            assert policy.is_active is True
            assert isinstance(policy.created_at, datetime)
            client.close()

    def test_get_logs_returns_logs_page(self, mock_response, valid_logs_response):
        """get_logs() returns LogsPage model."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, valid_logs_response)

            client = AIFirewall(api_key="af_test", project_id="test-project")
            logs = client.get_logs()

            assert isinstance(logs, LogsPage)
            assert logs.total == 1
            assert logs.page == 1
            assert logs.has_more is False
            assert len(logs.items) == 1
            assert isinstance(logs.items[0], AuditLogEntry)
            client.close()

    def test_get_logs_with_filters(self, mock_response, valid_logs_response):
        """get_logs() sends filter parameters correctly."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, valid_logs_response)

            client = AIFirewall(api_key="af_test", project_id="proj")
            client.get_logs(
                page=2,
                page_size=25,
                agent_name="specific-agent",
                allowed=True
            )

            call_args = mock_request.call_args
            params = call_args[1]["params"]
            assert params["page"] == 2
            assert params["page_size"] == 25
            assert params["agent_name"] == "specific-agent"
            assert params["allowed"] == "true"
            client.close()

    def test_get_stats_returns_dict(self, mock_response):
        """get_stats() returns dictionary."""
        stats_response = {
            "total_actions": 100,
            "allowed": 80,
            "blocked": 20,
            "block_rate": 0.2
        }
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, stats_response)

            client = AIFirewall(api_key="af_test", project_id="proj")
            stats = client.get_stats()

            assert isinstance(stats, dict)
            assert stats["total_actions"] == 100
            assert stats["block_rate"] == 0.2
            client.close()

    def test_update_policy_returns_policy(self, mock_response, valid_policy_response):
        """update_policy() returns updated Policy model."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, valid_policy_response)

            client = AIFirewall(api_key="af_test", project_id="proj")
            policy = client.update_policy(
                rules=[{"action_type": "*", "rate_limit": {"max": 100}}],
                name="new-policy",
                version="2.0"
            )

            assert isinstance(policy, Policy)
            call_args = mock_request.call_args
            assert call_args[1]["json"]["name"] == "new-policy"
            assert call_args[1]["json"]["version"] == "2.0"
            client.close()


# =============================================================================
# RETRY BEHAVIOR TESTS (DOCUMENTING CURRENT BEHAVIOR)
# =============================================================================

class TestRetryBehavior:
    """Tests documenting current retry behavior (no automatic retries)."""

    def test_no_automatic_retry_on_network_error(self):
        """Network errors are NOT automatically retried."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection failed")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(NetworkError):
                client.execute("agent", "action", {})

            # Verify request was only called once (no retries)
            assert mock_request.call_count == 1
            client.close()

    def test_no_retry_on_server_error(self, mock_response):
        """Server errors (5xx) are NOT automatically retried."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(503, {}, "Service Unavailable")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(AIFirewallError):
                client.execute("agent", "action", {})

            # Verify request was only called once (no retries)
            assert mock_request.call_count == 1
            client.close()

    def test_no_retry_on_timeout(self):
        """Timeout errors are NOT automatically retried."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Timeout")

            client = AIFirewall(api_key="af_test", project_id="proj")

            with pytest.raises(NetworkError):
                client.execute("agent", "action", {})

            # Verify request was only called once (no retries)
            assert mock_request.call_count == 1
            client.close()

    def test_single_request_per_execute_call(
        self, mock_response, valid_validation_response
    ):
        """Each execute() makes exactly one HTTP request."""
        with patch.object(httpx.Client, 'request') as mock_request:
            mock_request.return_value = mock_response(200, valid_validation_response)

            client = AIFirewall(api_key="af_test", project_id="proj")

            # Make multiple execute calls
            client.execute("agent", "action1", {})
            client.execute("agent", "action2", {})
            client.execute("agent", "action3", {})

            # Each call should result in exactly one request
            assert mock_request.call_count == 3
            client.close()


# =============================================================================
# MODEL TESTS
# =============================================================================

class TestModels:
    """Tests for data model classes."""

    def test_validation_result_from_dict(self):
        """ValidationResult.from_dict() parses correctly."""
        data = {
            "allowed": True,
            "action_id": "act_123",
            "timestamp": "2025-01-01T12:00:00Z",
            "reason": None,
            "execution_time_ms": 10
        }
        result = ValidationResult.from_dict(data)

        assert result.allowed is True
        assert result.action_id == "act_123"
        assert result.execution_time_ms == 10
        assert isinstance(result.timestamp, datetime)

    def test_validation_result_with_reason(self):
        """ValidationResult handles blocked action with reason."""
        data = {
            "allowed": False,
            "action_id": "act_456",
            "timestamp": "2025-01-01T12:00:00Z",
            "reason": "Rate limit exceeded",
            "execution_time_ms": 5
        }
        result = ValidationResult.from_dict(data)

        assert result.allowed is False
        assert result.reason == "Rate limit exceeded"

    def test_policy_from_dict(self):
        """Policy.from_dict() parses correctly."""
        data = {
            "id": 42,
            "project_id": "proj",
            "name": "my-policy",
            "version": "2.0",
            "rules": {"default": "block"},
            "is_active": True,
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-02T15:30:00Z"
        }
        policy = Policy.from_dict(data)

        assert policy.id == 42
        assert policy.name == "my-policy"
        assert policy.version == "2.0"
        assert policy.is_active is True

    def test_audit_log_entry_from_dict(self):
        """AuditLogEntry.from_dict() parses correctly."""
        data = {
            "action_id": "act_789",
            "project_id": "proj",
            "agent_name": "agent",
            "action_type": "do_thing",
            "params": {"key": "value"},
            "allowed": True,
            "reason": None,
            "policy_version": "1.0",
            "execution_time_ms": 3,
            "timestamp": "2025-01-01T14:00:00Z"
        }
        entry = AuditLogEntry.from_dict(data)

        assert entry.action_id == "act_789"
        assert entry.agent_name == "agent"
        assert entry.params == {"key": "value"}

    def test_logs_page_from_dict(self):
        """LogsPage.from_dict() parses correctly with nested items."""
        data = {
            "items": [
                {
                    "action_id": "act_001",
                    "project_id": "proj",
                    "agent_name": "agent1",
                    "action_type": "action1",
                    "params": {},
                    "allowed": True,
                    "reason": None,
                    "policy_version": "1.0",
                    "execution_time_ms": 5,
                    "timestamp": "2025-01-01T10:00:00Z"
                },
                {
                    "action_id": "act_002",
                    "project_id": "proj",
                    "agent_name": "agent2",
                    "action_type": "action2",
                    "params": {},
                    "allowed": False,
                    "reason": "Blocked",
                    "policy_version": "1.0",
                    "execution_time_ms": 3,
                    "timestamp": "2025-01-01T11:00:00Z"
                }
            ],
            "total": 50,
            "page": 1,
            "page_size": 2,
            "has_more": True
        }
        logs_page = LogsPage.from_dict(data)

        assert len(logs_page.items) == 2
        assert logs_page.total == 50
        assert logs_page.has_more is True
        assert isinstance(logs_page.items[0], AuditLogEntry)
        assert logs_page.items[0].agent_name == "agent1"
        assert logs_page.items[1].allowed is False
