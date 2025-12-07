# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-07

### Added

#### Server
- FastAPI-based API server with async SQLite database
- Project management endpoints (create, get, deactivate)
- Policy management with version history
- Action validation endpoint (`POST /validate_action`)
- Audit logging with pagination and filtering
- Log statistics endpoint

#### Policy Engine
- Parameter constraints: max, min, in, not_in, pattern, equals
- Agent restrictions: allowed_agents, blocked_agents
- Rate limiting per agent/action combination
- Nested parameter support with dot notation
- Default allow/block behavior
- Wildcard action type matching

#### Python SDK
- `AIFirewall` client class
- `execute()` method for action validation
- Policy management: `get_policy()`, `update_policy()`
- Audit logs: `get_logs()`, `get_stats()`
- Strict mode with `ActionBlockedError`
- Context manager support
- Custom exceptions for error handling

#### Integration Examples
- CrewAI integration patterns (decorator, context manager, wrapper)
- OpenAI Agents integration with ProtectedToolExecutor

#### Deployment
- Dockerfile with multi-stage build
- docker-compose.yml for local development
- Deployment guides for Railway, Fly.io, Render, AWS, GCP

#### Documentation
- README with quick start guide
- API reference documentation
- Policy writing guide with examples
- SDK documentation with usage examples

### Security
- API key authentication
- Project-scoped access control
- Non-root Docker user
- CORS middleware (configurable)

---

## Roadmap

See `future.md` for planned features including:
- Web dashboard
- Advanced policy engine with AI-generated rules
- DLP and PII scanning
- Industry compliance templates
- Real-time streaming mode
- Additional integrations
