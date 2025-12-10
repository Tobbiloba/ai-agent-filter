/**
 * AI Firewall Node.js SDK
 *
 * Validate AI agent actions against policies before execution.
 *
 * @example
 * ```typescript
 * import { AIFirewall, ActionBlockedError } from "ai-firewall";
 *
 * const fw = new AIFirewall({
 *   apiKey: "af_your_api_key",
 *   projectId: "my-project",
 * });
 *
 * const result = await fw.execute("agent", "action", { param: "value" });
 * if (result.allowed) {
 *   // Proceed with action
 * } else {
 *   console.log(`Blocked: ${result.reason}`);
 * }
 * ```
 *
 * @packageDocumentation
 */

// Main client
export { AIFirewall } from "./client.js";

// Types
export type {
  AIFirewallOptions,
  ValidationResult,
  Policy,
  AuditLogEntry,
  LogsPage,
  Stats,
  UpdatePolicyOptions,
  GetLogsOptions,
} from "./types.js";

// Errors
export {
  AIFirewallError,
  AuthenticationError,
  ProjectNotFoundError,
  PolicyNotFoundError,
  ValidationError,
  RateLimitError,
  NetworkError,
  ActionBlockedError,
} from "./errors.js";
