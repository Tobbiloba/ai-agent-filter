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
 * ```
 */
export class AIFirewall {
  static readonly DEFAULT_BASE_URL = "http://localhost:8000";
  static readonly DEFAULT_TIMEOUT = 30000;

  private readonly apiKey: string;
  private readonly projectId: string;
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly strict: boolean;

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
  }

  /**
   * Validate an action before executing it.
   *
   * @param agentName - Name of the agent performing the action
   * @param actionType - Type of action being performed
   * @param params - Parameters for the action
   * @returns ValidationResult with allowed status, action_id, and reason if blocked
   * @throws ActionBlockedError if strict=true and action is blocked
   * @throws AuthenticationError if API key is invalid
   * @throws NetworkError if network request fails
   */
  async execute(
    agentName: string,
    actionType: string,
    params: Record<string, unknown> = {}
  ): Promise<ValidationResult> {
    const response = (await this.request("POST", "/validate_action", {
      project_id: this.projectId,
      agent_name: agentName,
      action_type: actionType,
      params,
    })) as ApiValidationResponse;

    const result = this.parseValidationResult(response);

    if (this.strict && !result.allowed) {
      throw new ActionBlockedError(
        result.reason ?? "Action blocked by policy",
        result.actionId
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
   * Make an HTTP request to the API.
   */
  private async request(
    method: string,
    path: string,
    body?: unknown
  ): Promise<unknown> {
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

      // Handle error responses
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

      if (!response.ok) {
        const text = await response.text();
        throw new AIFirewallError(
          `API error ${response.status}: ${text}`
        );
      }

      return response.json();
    } catch (error) {
      // Re-throw our own errors
      if (error instanceof AIFirewallError) {
        throw error;
      }

      // Handle timeout/abort
      if (error instanceof Error && error.name === "AbortError") {
        throw new NetworkError("Request timed out");
      }

      // Handle other network errors
      throw new NetworkError(`Network error: ${error}`);
    } finally {
      clearTimeout(timeoutId);
    }
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
