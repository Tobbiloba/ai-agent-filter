"""Custom exceptions for the AI Firewall SDK."""


class AIFirewallError(Exception):
    """Base exception for AI Firewall SDK."""

    pass


class AuthenticationError(AIFirewallError):
    """Raised when API key is invalid or missing."""

    pass


class ProjectNotFoundError(AIFirewallError):
    """Raised when the specified project doesn't exist."""

    pass


class PolicyNotFoundError(AIFirewallError):
    """Raised when no active policy exists for a project."""

    pass


class ValidationError(AIFirewallError):
    """Raised when request validation fails."""

    pass


class RateLimitError(AIFirewallError):
    """Raised when rate limit is exceeded."""

    pass


class NetworkError(AIFirewallError):
    """Raised when a network error occurs."""

    pass


class ActionBlockedError(AIFirewallError):
    """Raised when an action is blocked by policy (optional strict mode)."""

    def __init__(self, reason: str, action_id: str):
        self.reason = reason
        self.action_id = action_id
        super().__init__(f"Action blocked: {reason}")
