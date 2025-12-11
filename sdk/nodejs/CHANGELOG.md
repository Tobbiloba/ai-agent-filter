# Changelog

All notable changes to the AI Agent Filter Node.js SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-11

### Added

#### Core Features
- **`AIFirewall` client class** - Main entry point for validating AI agent actions
- **`execute()` method** - Validate actions before execution with full parameter support
- **`getPolicy()` method** - Retrieve active policy for a project
- **`updatePolicy()` method** - Create or update policies programmatically
- **`getLogs()` method** - Paginated audit log retrieval with filtering
- **`getStats()` method** - Get validation statistics (allowed/blocked counts, top agents)

#### Configuration Options
- Configurable API key and project ID
- Custom base URL support for self-hosted servers
- Request timeout configuration (default: 30s)
- **Strict mode** - Optionally throw `ActionBlockedError` on blocked actions

#### Retry Logic
- Automatic retry with exponential backoff on transient failures
- Configurable max retries (default: 3)
- Configurable retry delays with jitter to prevent thundering herd
- Retry on configurable HTTP status codes (default: 429, 500, 502, 503, 504)
- Optional retry on network errors

#### Simulation Mode
- **`simulate` option** - Test policies without creating audit log entries
- Useful for what-if testing and policy validation
- Simulations never throw `ActionBlockedError` even in strict mode

#### Error Handling
- `AIFirewallError` - Base error class for all SDK errors
- `AuthenticationError` - Invalid or missing API key (401/403)
- `ProjectNotFoundError` - Project doesn't exist (404)
- `PolicyNotFoundError` - No active policy for project (404)
- `ValidationError` - Invalid request format (422)
- `RateLimitError` - Rate limit exceeded (429)
- `NetworkError` - Connection failures and timeouts
- `ActionBlockedError` - Action blocked by policy (strict mode only)

#### TypeScript Support
- Full TypeScript definitions for all types
- Exported interfaces: `AIFirewallOptions`, `ValidationResult`, `Policy`, `AuditLogEntry`, `LogsPage`, `Stats`, `UpdatePolicyOptions`, `GetLogsOptions`, `ExecuteOptions`

#### Documentation
- Comprehensive README with:
  - Quick start guide
  - Full API reference
  - Error handling examples
  - Framework integrations (LangChain.js, Vercel AI SDK, Express.js, Next.js)
  - Advanced usage patterns
  - Troubleshooting guide

### Technical Details

- **Node.js 18+** required (uses native `fetch`)
- **Zero production dependencies** - only dev dependencies for testing
- Uses `AbortController` for request timeouts
- JSON serialization for all API communication
- Proper error stack trace preservation in custom error classes

---

## Future Releases

### Planned for 0.2.0
- [ ] Connection pooling for high-throughput scenarios
- [ ] Request batching API
- [ ] WebSocket support for real-time policy updates
- [ ] Automatic policy caching with TTL

### Planned for 0.3.0
- [ ] OpenTelemetry integration for distributed tracing
- [ ] Built-in Prometheus metrics export
- [ ] LangChain.js native integration package

---

## Migration Guide

### Upgrading from Pre-release Versions

If you were using an early development version, note the following changes:

1. **Package name changed** from `ai-firewall` to `@anthropic-ai/ai-firewall`
2. **Retry logic is now enabled by default** - Set `maxRetries: 0` to disable
3. **`simulated` field added to `ValidationResult`** - Check for simulated responses

---

## Links

- [GitHub Repository](https://github.com/ai-agent-filter/ai-agent-filter)
- [npm Package](https://www.npmjs.com/package/@anthropic-ai/ai-firewall)
- [Documentation](https://docs.aiagentfilter.com)
- [Issue Tracker](https://github.com/ai-agent-filter/ai-agent-filter/issues)
