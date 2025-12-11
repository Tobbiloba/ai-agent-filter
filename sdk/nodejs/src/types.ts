/**
 * TypeScript interfaces for the AI Firewall SDK.
 */

/**
 * Options for initializing the AIFirewall client.
 */
export interface AIFirewallOptions {
  /** Your project API key (starts with 'af_') */
  apiKey: string;
  /** Your project identifier */
  projectId: string;
  /** API base URL (default: http://localhost:8000) */
  baseUrl?: string;
  /** Request timeout in milliseconds (default: 30000) */
  timeout?: number;
  /** If true, raise ActionBlockedError when actions are blocked */
  strict?: boolean;
  /** Maximum number of retry attempts (default: 3, set to 0 to disable) */
  maxRetries?: number;
  /** Base delay in milliseconds for exponential backoff (default: 1000) */
  retryBaseDelay?: number;
  /** Maximum delay cap in milliseconds (default: 30000) */
  retryMaxDelay?: number;
  /** HTTP status codes to retry on (default: [429, 500, 502, 503, 504]) */
  retryOnStatus?: number[];
  /** Whether to retry on network errors (default: true) */
  retryOnNetworkError?: boolean;
}

/**
 * Result of an action validation.
 */
export interface ValidationResult {
  /** Whether the action is allowed */
  allowed: boolean;
  /** Unique identifier for this validation (null for simulations) */
  actionId: string | null;
  /** When the validation occurred */
  timestamp: Date;
  /** Reason if the action was blocked */
  reason?: string;
  /** Validation execution time in milliseconds */
  executionTimeMs?: number;
  /** True if this was a simulation (no audit log created) */
  simulated: boolean;
}

/**
 * A project policy.
 */
export interface Policy {
  /** Policy database ID */
  id: number;
  /** Associated project ID */
  projectId: string;
  /** Policy name */
  name: string;
  /** Policy version string */
  version: string;
  /** Policy rules configuration */
  rules: Record<string, unknown>;
  /** Whether this policy is active */
  isActive: boolean;
  /** When the policy was created */
  createdAt: Date;
  /** When the policy was last updated */
  updatedAt: Date;
}

/**
 * An audit log entry.
 */
export interface AuditLogEntry {
  /** ID from validation */
  actionId: string;
  /** Associated project ID */
  projectId: string;
  /** Agent that performed the action */
  agentName: string;
  /** Type of action performed */
  actionType: string;
  /** Action parameters */
  params: Record<string, unknown>;
  /** Whether the action was allowed */
  allowed: boolean;
  /** Reason if blocked */
  reason?: string;
  /** Policy version used for validation */
  policyVersion?: string;
  /** Validation execution time in milliseconds */
  executionTimeMs?: number;
  /** When the action was validated */
  timestamp: Date;
}

/**
 * A page of audit logs.
 */
export interface LogsPage {
  /** Log entries in this page */
  items: AuditLogEntry[];
  /** Total number of logs */
  total: number;
  /** Current page number */
  page: number;
  /** Items per page */
  pageSize: number;
  /** Whether more pages exist */
  hasMore: boolean;
}

/**
 * Audit log statistics.
 */
export interface Stats {
  /** Total number of validation requests */
  totalActions: number;
  /** Number of allowed actions */
  allowed: number;
  /** Number of blocked actions */
  blocked: number;
  /** Block rate as percentage (0-100) */
  blockRate: number;
  /** Top action types by count */
  topActionTypes?: Array<{ actionType: string; count: number }>;
  /** Top agents by count */
  topAgents?: Array<{ agentName: string; count: number }>;
}

/**
 * Options for updating a policy.
 */
export interface UpdatePolicyOptions {
  /** Policy rules */
  rules: Array<Record<string, unknown>>;
  /** Policy name (default: "default") */
  name?: string;
  /** Policy version (default: "1.0") */
  version?: string;
  /** Default behavior when no rules match (default: "allow") */
  default?: "allow" | "block";
}

/**
 * Options for fetching audit logs.
 */
export interface GetLogsOptions {
  /** Page number (1-indexed, default: 1) */
  page?: number;
  /** Items per page (default: 50, max: 100) */
  pageSize?: number;
  /** Filter by agent name */
  agentName?: string;
  /** Filter by action type */
  actionType?: string;
  /** Filter by allowed status */
  allowed?: boolean;
}

/**
 * Options for executing an action validation.
 */
export interface ExecuteOptions {
  /** If true, run validation without logging or affecting state (what-if mode) */
  simulate?: boolean;
}

/**
 * API response types (internal use)
 */
export interface ApiValidationResponse {
  allowed: boolean;
  action_id: string | null;
  timestamp: string;
  reason?: string;
  execution_time_ms?: number;
  simulated: boolean;
}

export interface ApiPolicyResponse {
  id: number;
  project_id: string;
  name: string;
  version: string;
  rules: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiAuditLogResponse {
  action_id: string;
  project_id: string;
  agent_name: string;
  action_type: string;
  params: Record<string, unknown>;
  allowed: boolean;
  reason?: string;
  policy_version?: string;
  execution_time_ms?: number;
  timestamp: string;
}

export interface ApiLogsPageResponse {
  items: ApiAuditLogResponse[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface ApiStatsResponse {
  total_actions: number;
  allowed: number;
  blocked: number;
  block_rate: number;
  top_action_types?: Array<{ action_type: string; count: number }>;
  top_agents?: Array<{ agent_name: string; count: number }>;
}
