/**
 * AI Firewall client for validating agent actions.
 */

import {
  AIFirewallError,
  AuthenticationError,
  ProjectNotFoundError,
  PolicyNotFoundError,
  ValidationError,
  NetworkError,
  ActionBlockedError,
} from "./errors.js";

import type {
  AIFirewallOptions,
  ValidationResult,
  Policy,
  LogsPage,
  Stats,
  UpdatePolicyOptions,
  GetLogsOptions,
  ExecuteOptions,
  AuditLogEntry,
  ApiValidationResponse,
  ApiPolicyResponse,
  ApiLogsPageResponse,
  ApiStatsResponse,
  ApiAuditLogResponse,
} from "./types.js";

/**
 * AI Firewall client for validating agent actions.
 *
 * @example
 * ```typescript
 * const fw = new AIFirewall({
 *   apiKey: "af_xxx",
 *   projectId: "my-project",
 *   baseUrl: "http://localhost:8000"
 * });
 *
 * // Validate an action
 * const result = await fw.execute("my_agent", "do_something", { param: "value" });
 * if (result.allowed) {
 *   // proceed with action
 * } else {
 *   console.log(`Blocked: ${result.reason}`);
 * }
 *
 * // Or use strict mode (throws if blocked)
 * const fwStrict = new AIFirewall({ ...options, strict: true });
 * const result = await fwStrict.execute(...); // Throws ActionBlockedError if blocked
 *
 * // With retry configuration
 * const fwRetry = new AIFirewall({
 *   apiKey: "af_xxx",
 *   projectId: "my-project",
 *   maxRetries: 3,
 *   retryBaseDelay: 1000,
 * });
 * ```
 */
export class AIFirewall {
  static readonly DEFAULT_BASE_URL = "http://localhost:8000";
  static readonly DEFAULT_TIMEOUT = 30000;
  static readonly DEFAULT_MAX_RETRIES = 3;
  static readonly DEFAULT_RETRY_BASE_DELAY = 1000;
  static readonly DEFAULT_RETRY_MAX_DELAY = 30000;
  static readonly DEFAULT_RETRY_STATUS_CODES = new Set([429, 500, 502, 503, 504]);

  private readonly apiKey: string;
  private readonly projectId: string;
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly strict: boolean;
  private readonly maxRetries: number;
  private readonly retryBaseDelay: number;
  private readonly retryMaxDelay: number;
  private readonly retryOnStatus: Set<number>;
  private readonly retryOnNetworkError: boolean;

  /**
   * Initialize the AI Firewall client.
   *
   * @param options - Configuration options
   */
  constructor(options: AIFirewallOptions) {
    this.apiKey = options.apiKey;
    this.projectId = options.projectId;
    this.baseUrl = (options.baseUrl ?? AIFirewall.DEFAULT_BASE_URL).replace(
      /\/$/,
      ""
    );
    this.timeout = options.timeout ?? AIFirewall.DEFAULT_TIMEOUT;
    this.strict = options.strict ?? false;

    // Retry configuration
    this.maxRetries = options.maxRetries ?? AIFirewall.DEFAULT_MAX_RETRIES;
    this.retryBaseDelay = options.retryBaseDelay ?? AIFirewall.DEFAULT_RETRY_BASE_DELAY;
    this.retryMaxDelay = options.retryMaxDelay ?? AIFirewall.DEFAULT_RETRY_MAX_DELAY;
    this.retryOnStatus = new Set(options.retryOnStatus ?? AIFirewall.DEFAULT_RETRY_STATUS_CODES);
    this.retryOnNetworkError = options.retryOnNetworkError ?? true;
  }

  /**
   * Validate an action before executing it.
   *
   * @param agentName - Name of the agent performing the action
   * @param actionType - Type of action being performed
   * @param params - Parameters for the action
   * @param options - Optional settings including simulate mode
   * @returns ValidationResult with allowed status, action_id, and reason if blocked.
   *          For simulations, actionId will be null and simulated will be true.
   * @throws ActionBlockedError if strict=true and action is blocked (not thrown for simulations)
   * @throws AuthenticationError if API key is invalid
   * @throws NetworkError if network request fails
   */
  async execute(
    agentName: string,
    actionType: string,
    params: Record<string, unknown> = {},
    options: ExecuteOptions = {}
  ): Promise<ValidationResult> {
    const simulate = options.simulate ?? false;

    const response = (await this.request("POST", "/validate_action", {
      project_id: this.projectId,
      agent_name: agentName,
      action_type: actionType,
      params,
      simulate,
    })) as ApiValidationResponse;

    const result = this.parseValidationResult(response);

    // Don't raise ActionBlockedError for simulations (they're expected to test blocked scenarios)
    if (this.strict && !result.allowed && !simulate) {
      throw new ActionBlockedError(
        result.reason ?? "Action blocked by policy",
        result.actionId ?? "simulated"
      );
    }

    return result;
  }

  /**
   * Get the active policy for this project.
   *
   * @returns The active Policy
   * @throws PolicyNotFoundError if no active policy exists
   */
  async getPolicy(): Promise<Policy> {
    const response = (await this.request(
      "GET",
      `/policies/${this.projectId}`
    )) as ApiPolicyResponse;
    return this.parsePolicy(response);
  }

  /**
   * Update the policy for this project.
   *
   * @param options - Policy update options
   * @returns The updated Policy
   */
  async updatePolicy(options: UpdatePolicyOptions): Promise<Policy> {
    const payload = {
      name: options.name ?? "default",
      version: options.version ?? "1.0",
      default: options.default ?? "allow",
      rules: options.rules,
    };

    const response = (await this.request(
      "POST",
      `/policies/${this.projectId}`,
      payload
    )) as ApiPolicyResponse;
    return this.parsePolicy(response);
  }

  /**
   * Get audit logs for this project.
   *
   * @param options - Query options for filtering and pagination
   * @returns LogsPage with items and pagination info
   */
  async getLogs(options: GetLogsOptions = {}): Promise<LogsPage> {
    const params = new URLSearchParams();
    params.set("page", String(options.page ?? 1));
    params.set("page_size", String(options.pageSize ?? 50));

    if (options.agentName) {
      params.set("agent_name", options.agentName);
    }
    if (options.actionType) {
      params.set("action_type", options.actionType);
    }
    if (options.allowed !== undefined) {
      params.set("allowed", String(options.allowed));
    }

    const response = (await this.request(
      "GET",
      `/logs/${this.projectId}?${params.toString()}`
    )) as ApiLogsPageResponse;
    return this.parseLogsPage(response);
  }

  /**
   * Get audit log statistics for this project.
   *
   * @returns Statistics including total_actions, allowed, blocked, block_rate
   */
  async getStats(): Promise<Stats> {
    const response = (await this.request(
      "GET",
      `/logs/${this.projectId}/stats`
    )) as ApiStatsResponse;
    return this.parseStats(response);
  }

  /**
   * Close the client.
   * Note: This is a no-op for the fetch-based client (included for API parity with Python SDK).
   */
  close(): void {
    // No-op for fetch (no persistent connection)
  }

  /**
   * Calculate delay with exponential backoff and jitter.
   */
  private calculateBackoff(attempt: number): number {
    let delay = this.retryBaseDelay * Math.pow(2, attempt);
    delay = Math.min(delay, this.retryMaxDelay);
    // Add jitter (±25%) to prevent thundering herd
    const jitter = delay * 0.25 * (Math.random() * 2 - 1);
    return Math.max(0, delay + jitter);
  }

  /**
   * Check if the HTTP status code should be retried.
   */
  private isRetryableStatus(statusCode: number): boolean {
    return this.retryOnStatus.has(statusCode);
  }

  /**
   * Sleep for a specified duration.
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Handle error responses and throw appropriate exceptions.
   */
  private async handleResponseError(response: Response): Promise<never> {
    if (response.status === 401) {
      throw new AuthenticationError("Missing or invalid API key");
    }

    if (response.status === 403) {
      throw new AuthenticationError(
        "API key does not have access to this resource"
      );
    }

    if (response.status === 404) {
      const data = (await response.json()) as { detail?: string };
      const detail = data.detail ?? "";

      if (detail.toLowerCase().includes("policy")) {
        throw new PolicyNotFoundError(detail);
      }
      if (detail.toLowerCase().includes("project")) {
        throw new ProjectNotFoundError(detail);
      }
      throw new AIFirewallError(detail || "Resource not found");
    }

    if (response.status === 422) {
      const data = await response.json();
      throw new ValidationError(`Invalid request: ${JSON.stringify(data)}`);
    }

    const text = await response.text();
    throw new AIFirewallError(`API error ${response.status}: ${text}`);
  }

  /**
   * Make an HTTP request to the API with automatic retry on transient failures.
   *
   * Retries on:
   * - Network errors (connection refused, timeout, etc.) if retryOnNetworkError=true
   * - HTTP status codes in retryOnStatus (default: 429, 500, 502, 503, 504)
   *
   * Does NOT retry on:
   * - 401 Unauthorized (invalid API key)
   * - 403 Forbidden (access denied)
   * - 404 Not Found
   * - 422 Validation Error
   */
  private async request(
    method: string,
    path: string,
    body?: unknown
  ): Promise<unknown> {
    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);

      try {
        const url = `${this.baseUrl}${path}`;
        const response = await fetch(url, {
          method,
          headers: {
            "X-API-Key": this.apiKey,
            "Content-Type": "application/json",
          },
          body: body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        // Check if we got a retryable status code
        if (this.isRetryableStatus(response.status)) {
          if (attempt < this.maxRetries) {
            const delay = this.calculateBackoff(attempt);
            await this.sleep(delay);
            continue;
          }
          // Last attempt - throw the error
          await this.handleResponseError(response);
        }

        // Non-retryable error
        if (!response.ok) {
          await this.handleResponseError(response);
        }

        return response.json();
      } catch (error) {
        clearTimeout(timeoutId);

        // Re-throw our own errors (non-retryable)
        if (error instanceof AIFirewallError) {
          throw error;
        }

        // Handle timeout/abort
        if (error instanceof Error && error.name === "AbortError") {
          lastError = new NetworkError("Request timed out");
          if (!this.retryOnNetworkError || attempt >= this.maxRetries) {
            throw lastError;
          }
          const delay = this.calculateBackoff(attempt);
          await this.sleep(delay);
          continue;
        }

        // Handle other network errors
        lastError = new NetworkError(`Network error: ${error}`);
        if (!this.retryOnNetworkError || attempt >= this.maxRetries) {
          throw lastError;
        }
        const delay = this.calculateBackoff(attempt);
        await this.sleep(delay);
        continue;
      }
    }

    // Should not reach here, but handle edge case
    throw lastError ?? new AIFirewallError("Unexpected error in request retry loop");
  }

  /**
   * Parse API validation response to ValidationResult.
   */
  private parseValidationResult(data: ApiValidationResponse): ValidationResult {
    return {
      allowed: data.allowed,
      actionId: data.action_id,
      timestamp: new Date(data.timestamp.replace("Z", "")),
      reason: data.reason,
      executionTimeMs: data.execution_time_ms,
      simulated: data.simulated ?? false,
    };
  }

  /**
   * Parse API policy response to Policy.
   */
  private parsePolicy(data: ApiPolicyResponse): Policy {
    return {
      id: data.id,
      projectId: data.project_id,
      name: data.name,
      version: data.version,
      rules: data.rules,
      isActive: data.is_active,
      createdAt: new Date(data.created_at.replace("Z", "")),
      updatedAt: new Date(data.updated_at.replace("Z", "")),
    };
  }

  /**
   * Parse API audit log response to AuditLogEntry.
   */
  private parseAuditLogEntry(data: ApiAuditLogResponse): AuditLogEntry {
    return {
      actionId: data.action_id,
      projectId: data.project_id,
      agentName: data.agent_name,
      actionType: data.action_type,
      params: data.params,
      allowed: data.allowed,
      reason: data.reason,
      policyVersion: data.policy_version,
      executionTimeMs: data.execution_time_ms,
      timestamp: new Date(data.timestamp.replace("Z", "")),
    };
  }

  /**
   * Parse API logs page response to LogsPage.
   */
  private parseLogsPage(data: ApiLogsPageResponse): LogsPage {
    return {
      items: data.items.map((item) => this.parseAuditLogEntry(item)),
      total: data.total,
      page: data.page,
      pageSize: data.page_size,
      hasMore: data.has_more,
    };
  }

  /**
   * Parse API stats response to Stats.
   */
  private parseStats(data: ApiStatsResponse): Stats {
    return {
      totalActions: data.total_actions,
      allowed: data.allowed,
      blocked: data.blocked,
      blockRate: data.block_rate,
      topActionTypes: data.top_action_types?.map((item) => ({
        actionType: item.action_type,
        count: item.count,
      })),
      topAgents: data.top_agents?.map((item) => ({
        agentName: item.agent_name,
        count: item.count,
      })),
    };
  }
}
