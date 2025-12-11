/**
 * Unit tests for the AI Firewall SDK.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  AIFirewall,
  AIFirewallError,
  AuthenticationError,
  ProjectNotFoundError,
  PolicyNotFoundError,
  ValidationError,
  NetworkError,
  ActionBlockedError,
} from "../src/index.js";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("AIFirewall", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("constructor", () => {
    it("uses default base URL when not provided", () => {
      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
      });
      expect(fw).toBeInstanceOf(AIFirewall);
    });

    it("strips trailing slash from base URL", () => {
      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        baseUrl: "http://localhost:8000/",
      });
      expect(fw).toBeInstanceOf(AIFirewall);
    });

    it("accepts custom timeout", () => {
      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        timeout: 5000,
      });
      expect(fw).toBeInstanceOf(AIFirewall);
    });

    it("accepts strict mode option", () => {
      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        strict: true,
      });
      expect(fw).toBeInstanceOf(AIFirewall);
    });

    it("accepts retry configuration options", () => {
      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 5,
        retryBaseDelay: 500,
        retryMaxDelay: 10000,
        retryOnStatus: [429, 503],
        retryOnNetworkError: false,
      });
      expect(fw).toBeInstanceOf(AIFirewall);
    });
  });

  describe("execute", () => {
    it("returns ValidationResult on successful validation", async () => {
      const mockResponse = {
        allowed: true,
        action_id: "act_123",
        timestamp: "2025-01-01T12:00:00Z",
        execution_time_ms: 5,
        simulated: false,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0, // Disable retries for test
      });

      const result = await fw.execute("test-agent", "test-action", {
        param: "value",
      });

      expect(result.allowed).toBe(true);
      expect(result.actionId).toBe("act_123");
      expect(result.timestamp).toBeInstanceOf(Date);
      expect(result.executionTimeMs).toBe(5);
      expect(result.simulated).toBe(false);

      // Verify fetch was called with correct URL and method
      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/validate_action",
        expect.objectContaining({
          method: "POST",
          headers: {
            "X-API-Key": "af_test",
            "Content-Type": "application/json",
          },
        })
      );

      // Verify request body contains expected fields
      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      expect(body.project_id).toBe("test-project");
      expect(body.agent_name).toBe("test-agent");
      expect(body.action_type).toBe("test-action");
      expect(body.params).toEqual({ param: "value" });
      expect(body.simulate).toBe(false);
    });

    it("returns blocked result with reason", async () => {
      const mockResponse = {
        allowed: false,
        action_id: "act_456",
        timestamp: "2025-01-01T12:00:00Z",
        reason: "Amount exceeds maximum limit",
        execution_time_ms: 3,
        simulated: false,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      const result = await fw.execute("test-agent", "pay_invoice", {
        amount: 50000,
      });

      expect(result.allowed).toBe(false);
      expect(result.reason).toBe("Amount exceeds maximum limit");
    });

    it("throws ActionBlockedError in strict mode when blocked", async () => {
      const mockResponse = {
        allowed: false,
        action_id: "act_789",
        timestamp: "2025-01-01T12:00:00Z",
        reason: "Action not allowed",
        simulated: false,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        strict: true,
        maxRetries: 0,
      });

      await expect(
        fw.execute("test-agent", "forbidden-action", {})
      ).rejects.toThrow(ActionBlockedError);
    });

    it("does not throw in strict mode for simulations", async () => {
      const mockResponse = {
        allowed: false,
        action_id: null,
        timestamp: "2025-01-01T12:00:00Z",
        reason: "Would be blocked",
        simulated: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        strict: true,
        maxRetries: 0,
      });

      // Should NOT throw even though blocked because it's a simulation
      const result = await fw.execute("test-agent", "action", {}, { simulate: true });
      expect(result.allowed).toBe(false);
      expect(result.simulated).toBe(true);
    });

    it("uses default empty params when not provided", async () => {
      const mockResponse = {
        allowed: true,
        action_id: "act_000",
        timestamp: "2025-01-01T12:00:00Z",
        simulated: false,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      await fw.execute("agent", "action");

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      expect(body.params).toEqual({});
    });

    it("sends simulate flag in request body", async () => {
      const mockResponse = {
        allowed: true,
        action_id: null,
        timestamp: "2025-01-01T12:00:00Z",
        simulated: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      await fw.execute("agent", "action", {}, { simulate: true });

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      expect(body.simulate).toBe(true);
    });
  });

  describe("getPolicy", () => {
    it("returns Policy on success", async () => {
      const mockResponse = {
        id: 1,
        project_id: "test-project",
        name: "default",
        version: "1.0",
        rules: { default: "allow" },
        is_active: true,
        created_at: "2025-01-01T10:00:00Z",
        updated_at: "2025-01-01T10:00:00Z",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      const policy = await fw.getPolicy();

      expect(policy.id).toBe(1);
      expect(policy.projectId).toBe("test-project");
      expect(policy.name).toBe("default");
      expect(policy.isActive).toBe(true);
      expect(policy.createdAt).toBeInstanceOf(Date);
    });

    it("throws PolicyNotFoundError when no policy exists", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: "No active policy found for project" }),
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      await expect(fw.getPolicy()).rejects.toThrow(PolicyNotFoundError);
    });
  });

  describe("updatePolicy", () => {
    it("returns updated Policy on success", async () => {
      const mockResponse = {
        id: 2,
        project_id: "test-project",
        name: "new-policy",
        version: "2.0",
        rules: [{ action_type: "*", rate_limit: { max_requests: 100 } }],
        is_active: true,
        created_at: "2025-01-01T12:00:00Z",
        updated_at: "2025-01-01T12:00:00Z",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      const policy = await fw.updatePolicy({
        rules: [{ action_type: "*", rate_limit: { max_requests: 100 } }],
        name: "new-policy",
        version: "2.0",
      });

      expect(policy.name).toBe("new-policy");
      expect(policy.version).toBe("2.0");
    });

    it("uses default values for name, version, and default", async () => {
      const mockResponse = {
        id: 3,
        project_id: "test-project",
        name: "default",
        version: "1.0",
        rules: [],
        is_active: true,
        created_at: "2025-01-01T12:00:00Z",
        updated_at: "2025-01-01T12:00:00Z",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      await fw.updatePolicy({ rules: [] });

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      expect(body.name).toBe("default");
      expect(body.version).toBe("1.0");
      expect(body.default).toBe("allow");
      expect(body.rules).toEqual([]);
    });
  });

  describe("getLogs", () => {
    it("returns LogsPage on success", async () => {
      const mockResponse = {
        items: [
          {
            action_id: "log_123",
            project_id: "test-project",
            agent_name: "test-agent",
            action_type: "test-action",
            params: {},
            allowed: true,
            reason: null,
            policy_version: "1.0",
            execution_time_ms: 5,
            timestamp: "2025-01-01T12:00:00Z",
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        has_more: false,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      const logs = await fw.getLogs();

      expect(logs.items).toHaveLength(1);
      expect(logs.items[0].actionId).toBe("log_123");
      expect(logs.items[0].agentName).toBe("test-agent");
      expect(logs.total).toBe(1);
      expect(logs.hasMore).toBe(false);
    });

    it("includes filter parameters in request", async () => {
      const mockResponse = {
        items: [],
        total: 0,
        page: 2,
        page_size: 25,
        has_more: false,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      await fw.getLogs({
        page: 2,
        pageSize: 25,
        agentName: "invoice_agent",
        actionType: "pay_invoice",
        allowed: false,
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("page=2"),
        expect.any(Object)
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("page_size=25"),
        expect.any(Object)
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("agent_name=invoice_agent"),
        expect.any(Object)
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("action_type=pay_invoice"),
        expect.any(Object)
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("allowed=false"),
        expect.any(Object)
      );
    });
  });

  describe("getStats", () => {
    it("returns Stats on success", async () => {
      const mockResponse = {
        total_actions: 100,
        allowed: 95,
        blocked: 5,
        block_rate: 5.0,
        top_action_types: [{ action_type: "pay_invoice", count: 50 }],
        top_agents: [{ agent_name: "invoice_agent", count: 80 }],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      const stats = await fw.getStats();

      expect(stats.totalActions).toBe(100);
      expect(stats.allowed).toBe(95);
      expect(stats.blocked).toBe(5);
      expect(stats.blockRate).toBe(5.0);
      expect(stats.topActionTypes?.[0].actionType).toBe("pay_invoice");
      expect(stats.topAgents?.[0].agentName).toBe("invoice_agent");
    });
  });

  describe("error handling", () => {
    it("throws AuthenticationError on 401", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Invalid API key" }),
      });

      const fw = new AIFirewall({
        apiKey: "invalid_key",
        projectId: "test-project",
        maxRetries: 0,
      });

      await expect(fw.execute("agent", "action", {})).rejects.toThrow(
        AuthenticationError
      );
    });

    it("throws AuthenticationError on 403", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: "Access denied" }),
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "wrong-project",
        maxRetries: 0,
      });

      await expect(fw.execute("agent", "action", {})).rejects.toThrow(
        AuthenticationError
      );
    });

    it("throws ProjectNotFoundError on 404 with project message", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Project 'unknown' not found" }),
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "unknown",
        maxRetries: 0,
      });

      await expect(fw.getPolicy()).rejects.toThrow(ProjectNotFoundError);
    });

    it("throws ValidationError on 422", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({
          detail: [{ loc: ["body", "agent_name"], msg: "field required" }],
        }),
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0,
      });

      await expect(fw.execute("", "action", {})).rejects.toThrow(
        ValidationError
      );
    });

    it("throws AIFirewallError on 500 after retries exhausted", async () => {
      // Mock all retry attempts to return 500
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        text: async () => "Internal Server Error",
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0, // Disable retries for immediate failure
      });

      await expect(fw.execute("agent", "action", {})).rejects.toThrow(
        AIFirewallError
      );
    });

    it("throws NetworkError on fetch failure after retries exhausted", async () => {
      mockFetch.mockRejectedValue(new Error("Connection refused"));

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 0, // Disable retries for immediate failure
      });

      await expect(fw.execute("agent", "action", {})).rejects.toThrow(
        NetworkError
      );
    });

    it("throws NetworkError on timeout after retries exhausted", async () => {
      const abortError = new Error("The operation was aborted");
      abortError.name = "AbortError";
      mockFetch.mockRejectedValue(abortError);

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        timeout: 100,
        maxRetries: 0, // Disable retries for immediate failure
      });

      await expect(fw.execute("agent", "action", {})).rejects.toThrow(
        NetworkError
      );
    });

    it("retries on 500 status codes", async () => {
      // First call returns 500, second succeeds
      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 500,
          text: async () => "Internal Server Error",
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({
            allowed: true,
            action_id: "act_123",
            timestamp: "2025-01-01T12:00:00Z",
            simulated: false,
          }),
        });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 1,
        retryBaseDelay: 1, // Very short delay for test
      });

      const result = await fw.execute("agent", "action", {});
      expect(result.allowed).toBe(true);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it("retries on network errors", async () => {
      // First call fails with network error, second succeeds
      mockFetch
        .mockRejectedValueOnce(new Error("Connection refused"))
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({
            allowed: true,
            action_id: "act_123",
            timestamp: "2025-01-01T12:00:00Z",
            simulated: false,
          }),
        });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        maxRetries: 1,
        retryBaseDelay: 1, // Very short delay for test
      });

      const result = await fw.execute("agent", "action", {});
      expect(result.allowed).toBe(true);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it("does not retry on 401/403/404/422", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Invalid API key" }),
      });

      const fw = new AIFirewall({
        apiKey: "invalid_key",
        projectId: "test-project",
        maxRetries: 3, // Would retry if this was a retryable error
        retryBaseDelay: 1,
      });

      await expect(fw.execute("agent", "action", {})).rejects.toThrow(
        AuthenticationError
      );
      // Should only be called once (no retries)
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });

  describe("close", () => {
    it("can be called without error", () => {
      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
      });

      expect(() => fw.close()).not.toThrow();
    });
  });
});

describe("Error classes", () => {
  it("AIFirewallError has correct name", () => {
    const error = new AIFirewallError("test");
    expect(error.name).toBe("AIFirewallError");
    expect(error.message).toBe("test");
  });

  it("ActionBlockedError has reason and actionId", () => {
    const error = new ActionBlockedError("limit exceeded", "act_123");
    expect(error.name).toBe("ActionBlockedError");
    expect(error.reason).toBe("limit exceeded");
    expect(error.actionId).toBe("act_123");
    expect(error.message).toBe("Action blocked: limit exceeded");
  });

  it("All error classes extend AIFirewallError", () => {
    expect(new AuthenticationError()).toBeInstanceOf(AIFirewallError);
    expect(new ProjectNotFoundError()).toBeInstanceOf(AIFirewallError);
    expect(new PolicyNotFoundError()).toBeInstanceOf(AIFirewallError);
    expect(new ValidationError()).toBeInstanceOf(AIFirewallError);
    expect(new NetworkError()).toBeInstanceOf(AIFirewallError);
    expect(new ActionBlockedError("r", "id")).toBeInstanceOf(AIFirewallError);
  });
});
