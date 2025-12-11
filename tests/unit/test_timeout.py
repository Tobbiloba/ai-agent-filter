"""
Unit tests for request timeout configuration.

Tests:
- Timeout middleware returns 504 with structured error
- Config loads timeout values from environment
- Webhook service uses config timeout
- Policy engine uses config timeout
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request
from fastapi.responses import JSONResponse

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestRequestTimeoutMiddleware:
    """Tests for RequestTimeoutMiddleware."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        from server.middleware.timeout import RequestTimeoutMiddleware
        app = MagicMock()
        return RequestTimeoutMiddleware(app, timeout=1.0)

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/validate_action"
        return request

    @pytest.mark.asyncio
    async def test_returns_response_when_fast(self, middleware, mock_request):
        """Should return response when request completes in time."""
        expected_response = JSONResponse(content={"success": True})

        async def fast_handler(request):
            return expected_response

        call_next = AsyncMock(side_effect=fast_handler)

        response = await middleware.dispatch(mock_request, call_next)

        assert response == expected_response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_returns_504_on_timeout(self, middleware, mock_request):
        """Should return 504 with structured error when request times out."""
        async def slow_handler(request):
            await asyncio.sleep(5)  # Longer than 1s timeout
            return JSONResponse(content={"success": True})

        call_next = AsyncMock(side_effect=slow_handler)

        response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 504
        # Parse response body
        import json
        body = json.loads(response.body.decode())
        assert "error" in body
        assert body["error"]["code"] == "request_timeout"
        assert "timed out" in body["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_uses_configured_timeout(self, mock_request):
        """Should use the configured timeout value."""
        from server.middleware.timeout import RequestTimeoutMiddleware

        # Create middleware with 0.1s timeout
        app = MagicMock()
        middleware = RequestTimeoutMiddleware(app, timeout=0.1)

        async def slightly_slow_handler(request):
            await asyncio.sleep(0.2)  # Longer than 0.1s
            return JSONResponse(content={"success": True})

        call_next = AsyncMock(side_effect=slightly_slow_handler)

        response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 504


class TestTimeoutConfig:
    """Tests for timeout configuration settings."""

    def test_default_timeout_values(self):
        """Config should have correct default timeout values."""
        with patch.dict('os.environ', {}, clear=True):
            from server.config import Settings
            settings = Settings()

            assert settings.request_timeout == 30.0
            assert settings.webhook_timeout == 5.0
            assert settings.regex_timeout == 1.0

    def test_timeout_from_env_vars(self):
        """Config should load timeout values from environment."""
        env_vars = {
            'REQUEST_TIMEOUT': '60.0',
            'WEBHOOK_TIMEOUT': '10.0',
            'REGEX_TIMEOUT': '2.0',
        }
        with patch.dict('os.environ', env_vars):
            from server.config import Settings
            settings = Settings()

            assert settings.request_timeout == 60.0
            assert settings.webhook_timeout == 10.0
            assert settings.regex_timeout == 2.0


class TestWebhookServiceTimeout:
    """Tests for webhook service timeout configuration."""

    def test_uses_config_timeout_by_default(self):
        """WebhookService should use config timeout when not specified."""
        with patch('server.config.get_settings') as mock_settings:
            mock_settings.return_value.webhook_timeout = 7.5

            from server.services.webhook import WebhookService
            service = WebhookService()

            assert service.timeout == 7.5

    def test_custom_timeout_overrides_config(self):
        """WebhookService should use custom timeout when specified."""
        with patch('server.config.get_settings') as mock_settings:
            mock_settings.return_value.webhook_timeout = 7.5

            from server.services.webhook import WebhookService
            service = WebhookService(timeout=15.0)

            assert service.timeout == 15.0


class TestPolicyEngineTimeout:
    """Tests for policy engine regex timeout configuration."""

    def test_uses_config_regex_timeout(self):
        """Regex functions should use config timeout."""
        with patch('server.config.get_settings') as mock_settings:
            mock_settings.return_value.regex_timeout = 2.5

            from server.services.policy_engine import _get_regex_timeout
            timeout = _get_regex_timeout()

            assert timeout == 2.5

    def test_safe_regex_match_uses_config_timeout(self):
        """safe_regex_match should use config timeout by default."""
        with patch('server.services.policy_engine._get_regex_timeout', return_value=1.0):
            from server.services.policy_engine import safe_regex_match

            # Simple pattern that should match quickly
            result = safe_regex_match(r"test", "test string")
            assert result is True

    def test_safe_regex_search_uses_config_timeout(self):
        """safe_regex_search should use config timeout by default."""
        with patch('server.services.policy_engine._get_regex_timeout', return_value=1.0):
            from server.services.policy_engine import safe_regex_search

            # Simple pattern that should be found quickly
            result = safe_regex_search(r"string", "test string")
            assert result is True

    def test_custom_timeout_overrides_config(self):
        """Regex functions should accept custom timeout parameter."""
        from server.services.policy_engine import safe_regex_match

        # Even with very short timeout, simple patterns should work
        result = safe_regex_match(r"test", "test", timeout=0.5)
        assert result is True


class TestErrorResponse:
    """Tests for timeout error response format."""

    def test_request_timeout_error_code_exists(self):
        """REQUEST_TIMEOUT error code should exist."""
        from server.errors import ErrorCode
        assert hasattr(ErrorCode, 'REQUEST_TIMEOUT')
        assert ErrorCode.REQUEST_TIMEOUT.value == "request_timeout"

    def test_request_timeout_has_message(self):
        """REQUEST_TIMEOUT should have error message defined."""
        from server.errors import ErrorCode, ERROR_MESSAGES
        assert ErrorCode.REQUEST_TIMEOUT in ERROR_MESSAGES
        assert "message" in ERROR_MESSAGES[ErrorCode.REQUEST_TIMEOUT]
        assert "hint" in ERROR_MESSAGES[ErrorCode.REQUEST_TIMEOUT]

    def test_make_error_produces_correct_format(self):
        """make_error should produce correct format for REQUEST_TIMEOUT."""
        from server.errors import ErrorCode, make_error

        error = make_error(ErrorCode.REQUEST_TIMEOUT)

        assert "error" in error
        assert error["error"]["code"] == "request_timeout"
        assert "message" in error["error"]
        assert "hint" in error["error"]
