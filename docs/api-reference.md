# API Reference

Base URL: `http://localhost:8000` (or your deployed URL)

## Authentication

All endpoints except `/projects` (POST) and `/health` require an API key.

Include your API key in the `X-API-Key` header:

```
X-API-Key: af_your_api_key_here
```

---

## Endpoints

### Health Check

```
GET /health
```

Returns server health status.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

### Validate Action

```
POST /validate_action
```

Validate an AI agent action against the project's policy.

**Headers:**
- `X-API-Key`: Your project API key
- `Content-Type`: application/json

**Request Body:**
```json
{
  "project_id": "string",
  "agent_name": "string",
  "action_type": "string",
  "params": {}
}
```

**Response (Allowed):**
```json
{
  "allowed": true,
  "action_id": "act_abc123def456",
  "timestamp": "2025-12-07T10:30:00Z",
  "execution_time_ms": 1
}
```

**Response (Blocked):**
```json
{
  "allowed": false,
  "action_id": "act_xyz789uvw012",
  "timestamp": "2025-12-07T10:30:00Z",
  "reason": "Amount 15000 exceeds maximum allowed 10000",
  "execution_time_ms": 1
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/validate_action \
  -H "Content-Type: application/json" \
  -H "X-API-Key: af_xxx" \
  -d '{
    "project_id": "finbot-123",
    "agent_name": "invoice_agent",
    "action_type": "pay_invoice",
    "params": {"vendor": "Acme", "amount": 5000}
  }'
```

---

### Create Project

```
POST /projects
```

Create a new project and get an API key.

**Request Body:**
```json
{
  "id": "string",
  "name": "string"
}
```

**Response:**
```json
{
  "id": "my-project",
  "name": "My Project",
  "api_key": "af_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789",
  "is_active": true,
  "created_at": "2025-12-07T10:00:00Z"
}
```

⚠️ **Important**: Save the `api_key` - it cannot be retrieved again!

**Example:**
```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"id": "my-project", "name": "My AI Project"}'
```

---

### Get Project

```
GET /projects/{project_id}
```

Get project details (API key is partially hidden).

**Response:**
```json
{
  "id": "my-project",
  "name": "My Project",
  "api_key_preview": "af_aBcDeF...",
  "is_active": true,
  "created_at": "2025-12-07T10:00:00Z"
}
```

---

### Deactivate Project

```
DELETE /projects/{project_id}
```

Deactivate a project. All API calls for this project will be rejected.

**Response:**
```json
{
  "message": "Project 'my-project' has been deactivated"
}
```

---

### Get Policy

```
GET /policies/{project_id}
```

Get the active policy for a project.

**Headers:**
- `X-API-Key`: Your project API key

**Response:**
```json
{
  "id": 1,
  "project_id": "my-project",
  "name": "production",
  "version": "1.0",
  "rules": {
    "version": "1.0",
    "default": "allow",
    "rules": [...]
  },
  "is_active": true,
  "created_at": "2025-12-07T10:00:00Z",
  "updated_at": "2025-12-07T10:00:00Z"
}
```

---

### Create/Update Policy

```
POST /policies/{project_id}
```

Create or update the policy for a project. This deactivates any existing policy.

**Headers:**
- `X-API-Key`: Your project API key
- `Content-Type`: application/json

**Request Body:**
```json
{
  "name": "production",
  "version": "1.0",
  "default": "allow",
  "rules": [
    {
      "action_type": "pay_invoice",
      "constraints": {
        "params.amount": {"max": 10000}
      }
    }
  ]
}
```

**Response:** Same as Get Policy

**Example:**
```bash
curl -X POST http://localhost:8000/policies/my-project \
  -H "Content-Type: application/json" \
  -H "X-API-Key: af_xxx" \
  -d '{
    "name": "production",
    "version": "1.0",
    "default": "allow",
    "rules": [
      {
        "action_type": "pay_invoice",
        "constraints": {
          "params.amount": {"max": 10000, "min": 0},
          "params.currency": {"in": ["USD", "EUR"]}
        }
      }
    ]
  }'
```

---

### Get Policy History

```
GET /policies/{project_id}/history?limit=10
```

Get all policy versions (active and inactive).

**Query Parameters:**
- `limit`: Maximum number of policies to return (default: 10)

**Response:**
```json
[
  {
    "id": 2,
    "project_id": "my-project",
    "name": "production",
    "version": "2.0",
    "rules": {...},
    "is_active": true,
    "created_at": "2025-12-07T12:00:00Z",
    "updated_at": "2025-12-07T12:00:00Z"
  },
  {
    "id": 1,
    "project_id": "my-project",
    "name": "production",
    "version": "1.0",
    "rules": {...},
    "is_active": false,
    "created_at": "2025-12-07T10:00:00Z",
    "updated_at": "2025-12-07T12:00:00Z"
  }
]
```

---

### Get Audit Logs

```
GET /logs/{project_id}
```

Get audit logs with pagination and filters.

**Headers:**
- `X-API-Key`: Your project API key

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 50, max: 100)
- `agent_name`: Filter by agent name
- `action_type`: Filter by action type
- `allowed`: Filter by allowed status (true/false)

**Response:**
```json
{
  "items": [
    {
      "action_id": "act_abc123",
      "project_id": "my-project",
      "agent_name": "invoice_agent",
      "action_type": "pay_invoice",
      "params": {"vendor": "Acme", "amount": 5000},
      "allowed": true,
      "reason": null,
      "policy_version": "1.0",
      "execution_time_ms": 1,
      "timestamp": "2025-12-07T10:30:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 50,
  "has_more": true
}
```

**Example:**
```bash
# Get blocked actions only
curl "http://localhost:8000/logs/my-project?allowed=false&page_size=20" \
  -H "X-API-Key: af_xxx"
```

---

### Get Log Statistics

```
GET /logs/{project_id}/stats
```

Get summary statistics for audit logs.

**Headers:**
- `X-API-Key`: Your project API key

**Response:**
```json
{
  "total_actions": 1000,
  "allowed": 850,
  "blocked": 150,
  "block_rate": 15.0,
  "top_action_types": [
    {"action_type": "pay_invoice", "count": 500},
    {"action_type": "send_email", "count": 300}
  ],
  "top_agents": [
    {"agent_name": "invoice_agent", "count": 600},
    {"agent_name": "email_agent", "count": 300}
  ]
}
```

---

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Missing API key. Include it in the X-API-Key header."
}
```

### 403 Forbidden
```json
{
  "detail": "Invalid API key or project is inactive."
}
```

### 404 Not Found
```json
{
  "detail": "Project 'xyz' not found"
}
```

### 409 Conflict
```json
{
  "detail": "Project with ID 'my-project' already exists"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "project_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```
