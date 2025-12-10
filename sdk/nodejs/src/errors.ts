/**
 * Custom error classes for the AI Firewall SDK.
 */

/**
 * Base exception for AI Firewall SDK.
 */
export class AIFirewallError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AIFirewallError";
    // Maintains proper stack trace for where error was thrown (V8 engines)
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }
}

/**
 * Raised when API key is invalid or missing.
 */
export class AuthenticationError extends AIFirewallError {
  constructor(message: string = "Invalid or missing API key") {
    super(message);
    this.name = "AuthenticationError";
  }
}

/**
 * Raised when the specified project doesn't exist.
 */
export class ProjectNotFoundError extends AIFirewallError {
  constructor(message: string = "Project not found") {
    super(message);
    this.name = "ProjectNotFoundError";
  }
}

/**
 * Raised when no active policy exists for a project.
 */
export class PolicyNotFoundError extends AIFirewallError {
  constructor(message: string = "No active policy found") {
    super(message);
    this.name = "PolicyNotFoundError";
  }
}

/**
 * Raised when request validation fails.
 */
export class ValidationError extends AIFirewallError {
  constructor(message: string = "Request validation failed") {
    super(message);
    this.name = "ValidationError";
  }
}

/**
 * Raised when rate limit is exceeded.
 */
export class RateLimitError extends AIFirewallError {
  constructor(message: string = "Rate limit exceeded") {
    super(message);
    this.name = "RateLimitError";
  }
}

/**
 * Raised when a network error occurs.
 */
export class NetworkError extends AIFirewallError {
  constructor(message: string = "Network error occurred") {
    super(message);
    this.name = "NetworkError";
  }
}

/**
 * Raised when an action is blocked by policy (strict mode only).
 */
export class ActionBlockedError extends AIFirewallError {
  readonly reason: string;
  readonly actionId: string;

  constructor(reason: string, actionId: string) {
    super(`Action blocked: ${reason}`);
    this.name = "ActionBlockedError";
    this.reason = reason;
    this.actionId = actionId;
  }
}
