"""AI Firewall Python SDK Client."""

import random
import time
import httpx
from typing import Any

from ai_firewall.exceptions import (
    AIFirewallError,
    AuthenticationError,
    ProjectNotFoundError,
    PolicyNotFoundError,
    ValidationError,
    NetworkError,
    RateLimitError,
    ActionBlockedError,
)
from ai_firewall.models import ValidationResult, Policy, LogsPage


class AIFirewall:
    """
    AI Firewall client for validating agent actions.

    Usage:
        fw = AIFirewall(
            api_key="af_xxx",
            project_id="my-project",
            base_url="http://localhost:8000"  # or your deployed URL
        )

        # Validate an action
        result = fw.execute("my_agent", "do_something", {"param": "value"})
        if result.allowed:
            # proceed with action
            pass
        else:
            print(f"Blocked: {result.reason}")

        # Or use strict mode (raises exception if blocked)
        fw_strict = AIFirewall(..., strict=True)
        result = fw_strict.execute(...)  # Raises ActionBlockedError if blocked

        # With retry configuration
        fw_retry = AIFirewall(
            api_key="af_xxx",
            project_id="my-project",
            max_retries=3,
            retry_base_delay=1.0,
        )
    """

    DEFAULT_BASE_URL = "http://localhost:8000"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_BASE_DELAY = 1.0
    DEFAULT_RETRY_MAX_DELAY = 30.0
    DEFAULT_RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        api_key: str,
        project_id: str,
        base_url: str | None = None,
        timeout: float | None = None,
        strict: bool = False,
        max_retries: int | None = None,
        retry_base_delay: float | None = None,
        retry_max_delay: float | None = None,
        retry_on_status: set[int] | None = None,
        retry_on_network_error: bool = True,
    ):
        """
        Initialize the AI Firewall client.

        Args:
            api_key: Your project API key (starts with 'af_')
            project_id: Your project identifier
            base_url: API base URL (default: http://localhost:8000)
            timeout: Request timeout in seconds (default: 30)
            strict: If True, raise ActionBlockedError when actions are blocked
            max_retries: Maximum number of retry attempts (default: 3, set to 0 to disable)
            retry_base_delay: Base delay in seconds for exponential backoff (default: 1.0)
            retry_max_delay: Maximum delay cap in seconds (default: 30.0)
            retry_on_status: HTTP status codes to retry on (default: {429, 500, 502, 503, 504})
            retry_on_network_error: Whether to retry on network errors (default: True)
        """
        self.api_key = api_key
        self.project_id = project_id
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.strict = strict

        # Retry configuration
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        self.retry_base_delay = retry_base_delay or self.DEFAULT_RETRY_BASE_DELAY
        self.retry_max_delay = retry_max_delay or self.DEFAULT_RETRY_MAX_DELAY
        self.retry_on_status = retry_on_status or self.DEFAULT_RETRY_STATUS_CODES
        self.retry_on_network_error = retry_on_network_error

        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

    def execute(
        self,
        agent_name: str,
        action_type: str,
        params: dict[str, Any] | None = None,
        simulate: bool = False,
    ) -> ValidationResult:
        """
        Validate an action before executing it.

        Args:
            agent_name: Name of the agent performing the action
            action_type: Type of action being performed
            params: Parameters for the action
            simulate: If True, run validation without logging or affecting state
                     (what-if mode for testing policies)

        Returns:
            ValidationResult with allowed status, action_id, and reason if blocked.
            For simulations, action_id will be None and simulated will be True.

        Raises:
            ActionBlockedError: If strict=True and action is blocked (not raised for simulations)
            AuthenticationError: If API key is invalid
            NetworkError: If network request fails
        """
        payload = {
            "project_id": self.project_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "params": params or {},
            "simulate": simulate,
        }

        response = self._request("POST", "/validate_action", json=payload)
        result = ValidationResult.from_dict(response)

        # Don't raise ActionBlockedError for simulations (they're expected to test blocked scenarios)
        if self.strict and not result.allowed and not simulate:
            raise ActionBlockedError(
                reason=result.reason or "Action blocked by policy",
                action_id=result.action_id or "simulated",
            )

        return result

    def get_policy(self) -> Policy:
        """
        Get the active policy for this project.

        Returns:
            The active Policy

        Raises:
            PolicyNotFoundError: If no active policy exists
        """
        response = self._request("GET", f"/policies/{self.project_id}")
        return Policy.from_dict(response)

    def update_policy(
        self,
        rules: list[dict],
        name: str = "default",
        version: str = "1.0",
        default: str = "allow",
    ) -> Policy:
        """
        Update the policy for this project.

        Args:
            rules: List of policy rules
            name: Policy name
            version: Policy version string
            default: Default behavior ("allow" or "block")

        Returns:
            The updated Policy
        """
        payload = {
            "name": name,
            "version": version,
            "default": default,
            "rules": rules,
        }
        response = self._request("POST", f"/policies/{self.project_id}", json=payload)
        return Policy.from_dict(response)

    def get_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        agent_name: str | None = None,
        action_type: str | None = None,
        allowed: bool | None = None,
    ) -> LogsPage:
        """
        Get audit logs for this project.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page (max 100)
            agent_name: Filter by agent name
            action_type: Filter by action type
            allowed: Filter by allowed status

        Returns:
            LogsPage with items and pagination info
        """
        params = {"page": page, "page_size": page_size}
        if agent_name:
            params["agent_name"] = agent_name
        if action_type:
            params["action_type"] = action_type
        if allowed is not None:
            params["allowed"] = str(allowed).lower()

        response = self._request("GET", f"/logs/{self.project_id}", params=params)
        return LogsPage.from_dict(response)

    def get_stats(self) -> dict:
        """
        Get audit log statistics for this project.

        Returns:
            Dictionary with total_actions, allowed, blocked, block_rate, etc.
        """
        return self._request("GET", f"/logs/{self.project_id}/stats")

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate delay with exponential backoff and jitter.

        Args:
            attempt: The current attempt number (0-indexed)

        Returns:
            Delay in seconds with jitter applied
        """
        delay = self.retry_base_delay * (2 ** attempt)
        delay = min(delay, self.retry_max_delay)
        # Add jitter (±25%) to prevent thundering herd
        jitter = delay * 0.25 * (random.random() * 2 - 1)
        return max(0, delay + jitter)

    def _is_retryable_status(self, status_code: int) -> bool:
        """Check if the HTTP status code should be retried."""
        return status_code in self.retry_on_status

    def _handle_response_error(self, response: httpx.Response) -> None:
        """Handle error responses and raise appropriate exceptions."""
        if response.status_code == 401:
            raise AuthenticationError("Missing or invalid API key")
        if response.status_code == 403:
            raise AuthenticationError("API key does not have access to this resource")
        if response.status_code == 404:
            data = response.json()
            detail = data.get("detail", "")
            if "policy" in detail.lower():
                raise PolicyNotFoundError(detail)
            if "project" in detail.lower():
                raise ProjectNotFoundError(detail)
            raise AIFirewallError(detail)
        if response.status_code == 422:
            raise ValidationError(f"Invalid request: {response.json()}")
        if response.status_code == 429:
            raise RateLimitError("Rate limit exceeded")
        if response.status_code >= 400:
            raise AIFirewallError(f"API error {response.status_code}: {response.text}")

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict:
        """
        Make an HTTP request to the API with automatic retry on transient failures.

        Retries on:
        - Network errors (connection refused, timeout, etc.) if retry_on_network_error=True
        - HTTP status codes in retry_on_status (default: 429, 500, 502, 503, 504)

        Does NOT retry on:
        - 401 Unauthorized (invalid API key)
        - 403 Forbidden (access denied)
        - 404 Not Found
        - 422 Validation Error
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)

                # Check if we got a retryable status code
                if self._is_retryable_status(response.status_code):
                    if attempt < self.max_retries:
                        delay = self._calculate_backoff(attempt)
                        time.sleep(delay)
                        continue
                    # Last attempt - raise the error
                    self._handle_response_error(response)

                # Non-retryable error or success
                if response.status_code >= 400:
                    self._handle_response_error(response)

                return response.json()

            except httpx.RequestError as e:
                last_exception = e
                if not self.retry_on_network_error:
                    raise NetworkError(f"Network error: {e}") from e

                if attempt < self.max_retries:
                    delay = self._calculate_backoff(attempt)
                    time.sleep(delay)
                    continue

                # Last attempt - raise the error
                raise NetworkError(f"Network error after {attempt + 1} attempts: {e}") from e

        # Should not reach here, but handle edge case
        if last_exception:
            raise NetworkError(f"Max retries exceeded: {last_exception}") from last_exception
        raise AIFirewallError("Unexpected error in request retry loop")

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
