"""AI Firewall Python SDK Client."""

import httpx
from typing import Any

from ai_firewall.exceptions import (
    AIFirewallError,
    AuthenticationError,
    ProjectNotFoundError,
    PolicyNotFoundError,
    ValidationError,
    NetworkError,
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
    """

    DEFAULT_BASE_URL = "http://localhost:8000"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        api_key: str,
        project_id: str,
        base_url: str | None = None,
        timeout: float | None = None,
        strict: bool = False,
    ):
        """
        Initialize the AI Firewall client.

        Args:
            api_key: Your project API key (starts with 'af_')
            project_id: Your project identifier
            base_url: API base URL (default: http://localhost:8000)
            timeout: Request timeout in seconds (default: 30)
            strict: If True, raise ActionBlockedError when actions are blocked
        """
        self.api_key = api_key
        self.project_id = project_id
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.strict = strict

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
    ) -> ValidationResult:
        """
        Validate an action before executing it.

        Args:
            agent_name: Name of the agent performing the action
            action_type: Type of action being performed
            params: Parameters for the action

        Returns:
            ValidationResult with allowed status, action_id, and reason if blocked

        Raises:
            ActionBlockedError: If strict=True and action is blocked
            AuthenticationError: If API key is invalid
            NetworkError: If network request fails
        """
        payload = {
            "project_id": self.project_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "params": params or {},
        }

        response = self._request("POST", "/validate_action", json=payload)
        result = ValidationResult.from_dict(response)

        if self.strict and not result.allowed:
            raise ActionBlockedError(
                reason=result.reason or "Action blocked by policy",
                action_id=result.action_id,
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

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict:
        """Make an HTTP request to the API."""
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {e}") from e

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
        if response.status_code >= 400:
            raise AIFirewallError(f"API error {response.status_code}: {response.text}")

        return response.json()

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
