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
  });

  describe("execute", () => {
    it("returns ValidationResult on successful validation", async () => {
      const mockResponse = {
        allowed: true,
        action_id: "act_123",
        timestamp: "2025-01-01T12:00:00Z",
        execution_time_ms: 5,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
      });

      const result = await fw.execute("test-agent", "test-action", {
        param: "value",
      });

      expect(result.allowed).toBe(true);
      expect(result.actionId).toBe("act_123");
      expect(result.timestamp).toBeInstanceOf(Date);
      expect(result.executionTimeMs).toBe(5);

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/validate_action",
        expect.objectContaining({
          method: "POST",
          headers: {
            "X-API-Key": "af_test",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            project_id: "test-project",
            agent_name: "test-agent",
            action_type: "test-action",
            params: { param: "value" },
          }),
        })
      );
    });

    it("returns blocked result with reason", async () => {
      const mockResponse = {
        allowed: false,
        action_id: "act_456",
        timestamp: "2025-01-01T12:00:00Z",
        reason: "Amount exceeds maximum limit",
        execution_time_ms: 3,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
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
      });

      await expect(
        fw.execute("test-agent", "forbidden-action", {})
      ).rejects.toThrow(ActionBlockedError);

      try {
        await fw.execute("test-agent", "forbidden-action", {});
      } catch (error) {
        // Reset mock for second call
        mockFetch.mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => mockResponse,
        });
      }
    });

    it("uses default empty params when not provided", async () => {
      const mockResponse = {
        allowed: true,
        action_id: "act_000",
        timestamp: "2025-01-01T12:00:00Z",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
      });

      await fw.execute("agent", "action");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"params":{}'),
        })
      );
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
      });

      await fw.updatePolicy({ rules: [] });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({
            name: "default",
            version: "1.0",
            default: "allow",
            rules: [],
          }),
        })
      );
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
      });

      await expect(fw.execute("", "action", {})).rejects.toThrow(
        ValidationError
      );
    });

    it("throws AIFirewallError on other 4xx/5xx errors", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: async () => "Internal Server Error",
      });

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
      });

      await expect(fw.execute("agent", "action", {})).rejects.toThrow(
        AIFirewallError
      );
    });

    it("throws NetworkError on fetch failure", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Connection refused"));

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
      });

      await expect(fw.execute("agent", "action", {})).rejects.toThrow(
        NetworkError
      );
    });

    it("throws NetworkError on timeout", async () => {
      const abortError = new Error("The operation was aborted");
      abortError.name = "AbortError";
      mockFetch.mockRejectedValueOnce(abortError);

      const fw = new AIFirewall({
        apiKey: "af_test",
        projectId: "test-project",
        timeout: 100,
      });

      await expect(fw.execute("agent", "action", {})).rejects.toThrow(
        NetworkError
      );

      // Check the error message contains "timed out"
      mockFetch.mockRejectedValueOnce(abortError);
      try {
        await fw.execute("agent", "action", {});
      } catch (error) {
        expect((error as NetworkError).message).toContain("timed out");
      }
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
