# AI Agent Filter - Product Roadmap

> **Last Updated:** December 2024
> **Current Version:** 0.1.0
> **Status:** MVP Complete - Now Polishing

---

## Current State

### What's Built

| Feature | Status |
|---------|--------|
| FastAPI Server | Done |
| Policy Engine | Done |
| Parameter Constraints (min/max, in/not_in, patterns) | Done |
| Agent Permissions (allowed/blocked agents) | Done |
| Rate Limiting (per-agent, per-action) | Done |
| Audit Logging | Done |
| Python SDK | Done |
| CrewAI Integration | Done |
| OpenAI Agents Integration | Done |
| LangChain Integration | Done |
| SQLite Database | Done |
| Docker Support | Done |
| API Key Authentication | Done |

---

## 2-Week Sprint: Production Polish

**Goal:** Make it production-ready with unique features before public launch.

### Week 1: Production Readiness

| # | Feature | Priority | Complexity | Description |
|---|---------|----------|------------|-------------|
| 1.1 | PostgreSQL Support | Critical | Easy | Replace SQLite with PostgreSQL. Add connection pooling via `asyncpg`. ✓ Done |
| 1.2 | Redis Caching | Critical | Easy | Cache policy lookups. Sub-millisecond validation at scale. ✓ Done |
| 1.3 | Aggregate Limits | Critical | Medium | Cross-action limits: "max $50K total per day" with rolling windows. Key differentiator. ✓ Done |
| 1.4 | Fail-Closed Mode | Critical | Easy | Config: if service unreachable, block all actions (not fail-open). ✓ Done |
| 1.5 | `/metrics` Endpoint | High | Easy | Prometheus metrics: requests/sec, latency p50/p95/p99, error rates. ✓ Done |
| 1.6 | Structured Logging | High | Easy | JSON logs with correlation IDs. Compatible with log aggregators. ✓ Done |
| 1.7 | Graceful Shutdown | Medium | Easy | Drain connections on SIGTERM. Kubernetes-ready. ✓ Done |

**Week 1 Definition of Done:**
- [x] PostgreSQL works in production
- [x] Redis caching reduces latency to <5ms
- [x] Aggregate limits block circumvention attacks
- [x] `/metrics` endpoint returns Prometheus format
- [x] Structured logging with correlation IDs

---

### Week 2: Developer Experience

| # | Feature | Priority | Complexity | Description |
|---|---------|----------|------------|-------------|
| 2.1 | Policy Templates | Critical | Easy | Pre-built policies: Finance, Healthcare, General. Accelerates onboarding. ✓ Done |
| 2.2 | Node.js SDK | High | Medium | TypeScript/JavaScript support. Same API as Python SDK. ✓ Done |
| 2.3 | Webhook Notifications | High | Easy | POST to Slack/Discord/custom URL on blocked actions. ✓ Done |
| 2.4 | Better Error Messages | High | Easy | Actionable guidance in all error responses. ✓ Done |
| 2.5 | Policy Simulation | High | Medium | "What if" mode - test policies without affecting production. ✓ Done |
| 2.6 | SDK Retry Logic | Medium | Easy | Exponential backoff on transient failures. ✓ Done |
| 2.7 | Request Timeout Config | Medium | Easy | Configurable timeouts at server and SDK level. ✓ Done |

**Week 2 Definition of Done:**
- [x] 3 policy templates ready to use
- [x] Node.js SDK implemented with full API parity
- [x] Webhook fires on blocked actions
- [x] Better error messages with actionable guidance
- [x] Policy simulation returns "would block" results
- [x] SDK retry logic with exponential backoff
- [x] Configurable request timeouts at server and SDK level

---

## Week 3: Launch Preparation

| # | Item | Description |
|---|------|-------------|
| 3.1 | Landing Page | Single page with hero, problem/solution, code snippet, CTA ✓ Done |
| 3.2 | Blog Post 1 | "The $50,000 Mistake: Why Your AI Agent Needs Guardrails" |
| 3.3 | Blog Post 2 | "Building a Policy Engine for AI Agents in Python" |
| 3.4 | Blog Post 3 | "Add Safety Guardrails to Your LangChain Agent in 5 Minutes" |
| 3.5 | HN/Reddit Launch | Show HN post + r/LangChain, r/MachineLearning, r/Python |
| 3.6 | Enable GitHub Discussions | Community support without Discord overhead |

---

## Post-Launch: Security Hardening

| # | Feature | Priority | Complexity | Description |
|---|---------|----------|------------|-------------|
| 4.1 | Semantic Prompt Injection Detection | Critical | Hard | ML-based detection beyond regex patterns. |
| 4.2 | Action Chaining Detection | Critical | Hard | Detect split-transaction attacks (many small to bypass limits). |
| 4.3 | Secrets Detection | High | Medium | Block API keys, passwords, PII in parameters. |
| 4.4 | Cryptographic Audit Signing | High | Medium | Tamper-evident audit chain for compliance. |
| 4.5 | Request Signing (SDK) | High | Medium | HMAC signatures to prevent replay attacks. |
| 4.6 | IP Allowlisting | Medium | Easy | Restrict API access by IP per project. |
| 4.7 | API Key Rotation | Medium | Easy | Rotate keys without downtime. |

---

## Future: Enterprise Features

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 5.1 | SSO/OIDC | Critical | Okta, Azure AD, Google Workspace integration |
| 5.2 | RBAC | Critical | Admin, Policy Editor, Auditor, Viewer roles |
| 5.3 | Multi-Tenancy | Critical | Single deployment serves multiple orgs |
| 5.4 | Human-in-the-Loop | Critical | Slack/Teams approval for high-risk actions |
| 5.5 | Web Dashboard | Critical | Visual policy builder, monitoring, audit viewer |
| 5.6 | SIEM Export | High | Push logs to Splunk, Datadog, Elastic |
| 5.7 | Terraform Provider | High | Infrastructure-as-code for policies |

---

## Future: More Integrations

| Framework | Priority | Notes |
|-----------|----------|-------|
| AutoGen | High | Microsoft's framework |
| LlamaIndex | High | RAG-based agents |
| Haystack | Medium | deepset's framework |
| Semantic Kernel | Medium | Microsoft's SDK |
| Dify | Medium | Open-source LLM platform |
| Flowise | Medium | Low-code builder |
| Go SDK | High | High-performance needs |
| Java SDK | Low | Enterprise shops |
| .NET SDK | Low | Microsoft ecosystem |

---

## Technical Debt

| Item | Priority | Description |
|------|----------|-------------|
| Test Coverage >80% | Critical | Add integration + load tests |
| API Versioning | High | `/v1/` prefix for breaking changes |
| Database Migrations | Medium | Alembic for schema versioning |
| OpenAPI Docs | Medium | Auto-generated, always current |

---

## Success Metrics

### Week 2 (Production Ready)
- [ ] 10K validations/minute sustained
- [ ] <10ms p99 latency with Redis
- [ ] Zero data loss on restart
- [ ] Aggregate limits working

### Week 3 (Launch)
- [ ] Landing page live
- [ ] 3 blog posts published
- [ ] HN/Reddit posts submitted

### Week 4-6 (Traction)
- [ ] 50+ GitHub stars
- [ ] 5+ developers trying it
- [ ] First external contributor
- [ ] First testimonial

### Month 2-3 (Growth)
- [ ] 100+ GitHub stars
- [ ] 3 enterprise pilot conversations
- [ ] Node.js SDK published
- [ ] Community Discord if needed

---

## Competitive Positioning

| Competitor | Their Focus | Our Advantage |
|------------|-------------|---------------|
| Guardrails AI | LLM output validation | We validate **actions**, not just text |
| NeMo Guardrails | Conversation flow | We're lighter weight, action-focused |
| AWS Bedrock Guardrails | Content filtering | Cloud-agnostic, more flexible |
| Azure AI Content Safety | Harmful content | Behavioral safety, not content |

### Our Moat (Double Down Here)
1. **Action-Level Validation** - What AI does, not just says
2. **Cross-Action Intelligence** - Detect patterns across actions
3. **Agent Behavior Profiling** - Know when an agent is compromised
4. **Human-in-the-Loop** - Seamless approval workflows

---

## Architecture Evolution

### Current (v0.1)
```
┌─────────┐     ┌─────────────┐     ┌──────────┐
│   SDK   │────▶│  FastAPI    │────▶│  SQLite  │
└─────────┘     │  Server     │     └──────────┘
                └─────────────┘
```

### Target (v1.0)
```
┌─────────┐     ┌─────────────┐     ┌──────────┐
│   SDK   │────▶│   Gateway   │────▶│  Redis   │ (cache)
└─────────┘     │   (Auth)    │     └──────────┘
                └──────┬──────┘            │
                       │                   ▼
                       ▼            ┌──────────┐
                ┌─────────────┐     │ Postgres │ (persistence)
                │  Validator  │────▶└──────────┘
                │  Service    │            │
                └──────┬──────┘            ▼
                       │            ┌──────────┐
                       ▼            │  SIEM    │ (export)
                ┌─────────────┐     └──────────┘
                │  ML Service │
                │ (anomaly)   │
                └─────────────┘
```

---

## This Week's Focus

```
Week 1 Tasks:
[x] LangChain integration complete
[x] PostgreSQL support
[x] Redis caching
[x] Aggregate limits (daily totals)
[x] Fail-closed mode
[x] /metrics endpoint
[x] Structured logging
[x] Graceful shutdown
```

---

*This roadmap is a living document. Updated as priorities shift.*
