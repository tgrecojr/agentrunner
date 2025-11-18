# API Reference
**Multi-Agent Orchestration Platform**

Complete REST API documentation for all platform services.

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Common Patterns](#common-patterns)
4. [StateManager API (Port 8001)](#statemanager-api-port-8001)
5. [ConfigurationService API (Port 8002)](#configurationservice-api-port-8002)
6. [AgentOrchestrator API (Port 8003)](#agentorchestrator-api-port-8003)
7. [SchedulerService API (Port 8004)](#schedulerservice-api-port-8004)
8. [SlackGateway API (Port 8005)](#slackgateway-api-port-8005)
9. [Error Codes](#error-codes)
10. [Rate Limiting](#rate-limiting)
11. [WebSocket Events](#websocket-events)

---

## Overview

### Base URLs

| Service | Port | Base URL |
|---------|------|----------|
| StateManager | 8001 | `http://localhost:8001` |
| ConfigurationService | 8002 | `http://localhost:8002` |
| AgentOrchestrator | 8003 | `http://localhost:8003` |
| SchedulerService | 8004 | `http://localhost:8004` |
| SlackGateway | 8005 | `http://localhost:8005` |

### API Versioning

All APIs are currently version 1.0. Future versions will be accessed via `/v2/` prefix.

### Content Type

All APIs accept and return JSON:
```
Content-Type: application/json
```

---

## Authentication

### API Key Authentication

When `API_AUTH_ENABLED=true`, all requests require an API key:

```bash
curl -H "X-API-Key: your-api-key-here" http://localhost:8001/agents
```

### Slack Signature Verification

Slack webhook endpoints verify request signatures using HMAC-SHA256:

```python
import hmac
import hashlib
import time

timestamp = str(int(time.time()))
body = '{"type":"url_verification","challenge":"test"}'
signing_secret = "your-slack-signing-secret"

sig_basestring = f"v0:{timestamp}:{body}"
signature = 'v0=' + hmac.new(
    signing_secret.encode(),
    sig_basestring.encode(),
    hashlib.sha256
).hexdigest()

headers = {
    'X-Slack-Request-Timestamp': timestamp,
    'X-Slack-Signature': signature
}
```

---

## Common Patterns

### Health Check Endpoints

All services expose standard health check endpoints:

#### Liveness Probe
```http
GET /health/live
```

Returns 200 if service is running (for Kubernetes liveness probes).

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2025-11-18T10:30:00Z"
}
```

#### Readiness Probe
```http
GET /health/ready
```

Returns 200 if service is ready to accept traffic (for Kubernetes readiness probes).

**Response**:
```json
{
  "status": "ready",
  "timestamp": "2025-11-18T10:30:00Z",
  "dependencies": {
    "database": "ok",
    "cache": "ok",
    "message_queue": "ok"
  }
}
```

#### Detailed Health
```http
GET /health
```

Returns detailed health information with metrics.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-18T10:30:00Z",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "checks": {
    "database": "ok",
    "cache": "ok"
  },
  "metrics": {
    "requests_total": 12345,
    "requests_per_second": 10.5,
    "error_rate": 0.01
  }
}
```

### Pagination

List endpoints support pagination:

```http
GET /agents?offset=0&limit=20
```

**Parameters**:
- `offset`: Number of items to skip (default: 0)
- `limit`: Maximum items to return (default: 20, max: 100)

**Response**:
```json
{
  "items": [...],
  "total": 150,
  "offset": 0,
  "limit": 20,
  "has_more": true
}
```

### Filtering

List endpoints support filtering:

```http
GET /agents?execution_mode=autonomous&status=active
```

### Sorting

List endpoints support sorting:

```http
GET /agents?sort_by=created_at&sort_order=desc
```

**Parameters**:
- `sort_by`: Field name to sort by
- `sort_order`: `asc` or `desc` (default: `asc`)

---

## StateManager API (Port 8001)

### Agent State Management

#### Get Agent State

```http
GET /agents/{agent_name}/state
```

Retrieve current state for an agent.

**Path Parameters**:
- `agent_name` (string, required): Agent identifier

**Response** (200 OK):
```json
{
  "agent_name": "customer-support",
  "state_data": {
    "current_task": "helping_user_123",
    "context": {...}
  },
  "conversation_history": [
    {
      "role": "user",
      "content": "I need help with my account",
      "timestamp": "2025-11-18T10:25:00Z"
    },
    {
      "role": "assistant",
      "content": "I'd be happy to help. What seems to be the issue?",
      "timestamp": "2025-11-18T10:25:02Z"
    }
  ],
  "metadata": {
    "session_id": "sess_abc123",
    "user_id": "user_456"
  },
  "created_at": "2025-11-18T09:00:00Z",
  "updated_at": "2025-11-18T10:25:02Z",
  "last_activity": "2025-11-18T10:25:02Z"
}
```

**Error Responses**:
- `404 Not Found`: Agent state not found

#### Save Agent State

```http
POST /agents/{agent_name}/state
```

Save or update agent state.

**Path Parameters**:
- `agent_name` (string, required): Agent identifier

**Request Body**:
```json
{
  "state_data": {
    "current_task": "helping_user_123",
    "context": {
      "user_id": "user_456",
      "issue_type": "account_access"
    }
  },
  "conversation_history": [
    {
      "role": "user",
      "content": "I need help",
      "timestamp": "2025-11-18T10:25:00Z"
    }
  ],
  "metadata": {
    "session_id": "sess_abc123"
  }
}
```

**Response** (200 OK):
```json
{
  "agent_name": "customer-support",
  "saved_at": "2025-11-18T10:26:00Z",
  "version": 42
}
```

**Error Responses**:
- `400 Bad Request`: Invalid state data

#### Delete Agent State

```http
DELETE /agents/{agent_name}/state
```

Delete agent state (cleanup for removed agents).

**Path Parameters**:
- `agent_name` (string, required): Agent identifier

**Response** (204 No Content)

#### Append to Conversation History

```http
POST /agents/{agent_name}/conversation
```

Append messages to conversation history without replacing entire state.

**Path Parameters**:
- `agent_name` (string, required): Agent identifier

**Request Body**:
```json
{
  "messages": [
    {
      "role": "user",
      "content": "What's the status of my ticket?",
      "timestamp": "2025-11-18T10:27:00Z"
    },
    {
      "role": "assistant",
      "content": "Let me check that for you...",
      "timestamp": "2025-11-18T10:27:01Z"
    }
  ],
  "max_history": 100
}
```

**Response** (200 OK):
```json
{
  "agent_name": "customer-support",
  "messages_added": 2,
  "total_history": 45,
  "pruned": false
}
```

### Execution History

#### Get Execution History

```http
GET /executions
```

Retrieve execution history with filtering.

**Query Parameters**:
- `agent_name` (string, optional): Filter by agent
- `status` (string, optional): Filter by status (pending, running, completed, failed)
- `started_after` (ISO 8601, optional): Filter by start time
- `started_before` (ISO 8601, optional): Filter by start time
- `offset` (integer, optional): Pagination offset (default: 0)
- `limit` (integer, optional): Page size (default: 20, max: 100)

**Response** (200 OK):
```json
{
  "items": [
    {
      "execution_id": "exec_abc123",
      "agent_name": "data-analyzer",
      "task_type": "analysis",
      "status": "completed",
      "started_at": "2025-11-18T10:20:00Z",
      "completed_at": "2025-11-18T10:22:15Z",
      "duration_seconds": 135,
      "result": {
        "summary": "Analysis complete",
        "metrics": {...}
      },
      "trace_id": "trace_xyz789"
    }
  ],
  "total": 1542,
  "offset": 0,
  "limit": 20
}
```

#### Get Specific Execution

```http
GET /executions/{execution_id}
```

Get details for a specific execution.

**Path Parameters**:
- `execution_id` (string, required): Execution identifier

**Response** (200 OK):
```json
{
  "execution_id": "exec_abc123",
  "agent_name": "data-analyzer",
  "task_type": "analysis",
  "status": "completed",
  "started_at": "2025-11-18T10:20:00Z",
  "completed_at": "2025-11-18T10:22:15Z",
  "duration_seconds": 135,
  "result": {
    "summary": "Analysis complete",
    "data": {...}
  },
  "error_message": null,
  "trace_id": "trace_xyz789",
  "metadata": {
    "llm_provider": "openai",
    "llm_model": "gpt-4",
    "tokens_used": 1523,
    "cost": 0.045
  }
}
```

**Error Responses**:
- `404 Not Found`: Execution not found

### Cache Management

#### Clear Cache

```http
POST /cache/clear
```

Clear Redis cache (requires admin privileges).

**Request Body** (optional):
```json
{
  "pattern": "state:*",
  "confirm": true
}
```

**Response** (200 OK):
```json
{
  "cleared": true,
  "keys_deleted": 1523,
  "pattern": "state:*"
}
```

---

## ConfigurationService API (Port 8002)

### Agent Configuration Management

#### List All Agent Configurations

```http
GET /configs
```

Retrieve all agent configurations.

**Query Parameters**:
- `execution_mode` (string, optional): Filter by mode
- `tags` (string, optional): Comma-separated tags

**Response** (200 OK):
```json
{
  "configs": [
    {
      "name": "customer-support",
      "agent_type": "assistant",
      "execution_mode": "continuous",
      "llm_config": {
        "provider": "openai",
        "model": "gpt-4"
      },
      "tags": ["support", "customer-facing"],
      "created_at": "2025-11-18T09:00:00Z",
      "updated_at": "2025-11-18T10:00:00Z"
    }
  ],
  "total": 8
}
```

#### Get Specific Agent Configuration

```http
GET /configs/{agent_name}
```

Get full configuration for a specific agent.

**Path Parameters**:
- `agent_name` (string, required): Agent identifier

**Response** (200 OK):
```json
{
  "name": "customer-support",
  "agent_type": "assistant",
  "execution_mode": "continuous",
  "llm_config": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "system_prompt": "You are a helpful customer support agent...",
  "continuous_config": {
    "idle_timeout_seconds": 900,
    "save_interval_seconds": 180,
    "max_conversation_history": 100
  },
  "event_subscriptions": [
    "slack.command.support",
    "customer.ticket.created"
  ],
  "tools": [
    {
      "name": "knowledge_base",
      "type": "mcp",
      "url": "https://kb.example.com/mcp"
    }
  ],
  "tags": ["support", "customer-facing"],
  "created_at": "2025-11-18T09:00:00Z",
  "updated_at": "2025-11-18T10:00:00Z"
}
```

**Error Responses**:
- `404 Not Found`: Agent configuration not found

#### Validate Agent Configuration

```http
POST /configs/validate
```

Validate agent configuration without saving.

**Request Body**:
```json
{
  "name": "new-agent",
  "execution_mode": "autonomous",
  "llm_config": {
    "provider": "openai",
    "model": "gpt-4"
  },
  "system_prompt": "You are an assistant."
}
```

**Response** (200 OK):
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "No event_subscriptions defined - agent won't receive events"
  ]
}
```

**Response** (400 Bad Request) if invalid:
```json
{
  "valid": false,
  "errors": [
    "Missing required field: system_prompt",
    "Invalid execution_mode: invalid_mode"
  ],
  "warnings": []
}
```

#### Reload Configurations

```http
POST /reload
```

Manually trigger configuration reload from filesystem.

**Response** (200 OK):
```json
{
  "reloaded": true,
  "configs_loaded": 8,
  "configs_added": 1,
  "configs_updated": 2,
  "configs_removed": 0,
  "timestamp": "2025-11-18T10:30:00Z"
}
```

### Configuration File Management

#### Upload Configuration File

```http
POST /configs/upload
```

Upload a new agent configuration YAML file.

**Request** (multipart/form-data):
```
File: agent-config.yml
```

**Response** (201 Created):
```json
{
  "uploaded": true,
  "filename": "agent-config.yml",
  "agent_name": "new-agent",
  "path": "config/agents/agent-config.yml"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid YAML syntax
- `409 Conflict`: Agent with same name already exists

---

## AgentOrchestrator API (Port 8003)

### Agent Management

#### List All Agents

```http
GET /agents
```

List all registered agents with their status.

**Query Parameters**:
- `execution_mode` (string, optional): Filter by execution mode
- `status` (string, optional): Filter by health status (healthy, unhealthy, unresponsive)
- `tags` (string, optional): Comma-separated tags

**Response** (200 OK):
```json
{
  "agents": [
    {
      "name": "customer-support",
      "agent_type": "assistant",
      "execution_mode": "continuous",
      "status": "healthy",
      "registered_at": "2025-11-18T09:00:00Z",
      "last_health_check": "2025-11-18T10:29:45Z",
      "active_tasks": 2,
      "total_executions": 145,
      "success_rate": 0.98,
      "tags": ["support"]
    }
  ],
  "total": 8
}
```

#### Get Agent Details

```http
GET /agents/{agent_name}
```

Get detailed information about a specific agent.

**Path Parameters**:
- `agent_name` (string, required): Agent identifier

**Response** (200 OK):
```json
{
  "name": "customer-support",
  "agent_type": "assistant",
  "execution_mode": "continuous",
  "status": "healthy",
  "registered_at": "2025-11-18T09:00:00Z",
  "last_health_check": "2025-11-18T10:29:45Z",
  "configuration": {
    "llm_provider": "openai",
    "llm_model": "gpt-4",
    "event_subscriptions": ["slack.command.support"]
  },
  "metrics": {
    "active_tasks": 2,
    "total_executions": 145,
    "success_count": 142,
    "failure_count": 3,
    "success_rate": 0.98,
    "avg_duration_seconds": 4.2,
    "total_tokens_used": 45231,
    "total_cost": 1.35
  },
  "current_tasks": [
    {
      "execution_id": "exec_123",
      "started_at": "2025-11-18T10:28:00Z",
      "status": "running"
    }
  ]
}
```

**Error Responses**:
- `404 Not Found`: Agent not found

#### Get Agent Status

```http
GET /agents/{agent_name}/status
```

Get current status and health of an agent.

**Path Parameters**:
- `agent_name` (string, required): Agent identifier

**Response** (200 OK):
```json
{
  "name": "customer-support",
  "status": "healthy",
  "last_health_check": "2025-11-18T10:29:45Z",
  "response_time_ms": 45,
  "active_tasks": 2,
  "queue_depth": 5,
  "memory_usage_mb": 128,
  "uptime_seconds": 3600
}
```

### Task Submission

#### Submit Task to Agent

```http
POST /tasks
```

Submit a new task for agent execution.

**Request Body**:
```json
{
  "agent_name": "data-analyzer",
  "task_data": {
    "action": "analyze_dataset",
    "dataset_id": "ds_123",
    "parameters": {
      "analysis_type": "statistical",
      "output_format": "json"
    }
  },
  "priority": "normal",
  "timeout_seconds": 300,
  "callback_url": "https://api.example.com/callbacks/task-complete"
}
```

**Request Fields**:
- `agent_name` (string, required): Target agent
- `task_data` (object, required): Task-specific data
- `priority` (string, optional): low, normal, high (default: normal)
- `timeout_seconds` (integer, optional): Task timeout (default: 300)
- `callback_url` (string, optional): Webhook for completion notification

**Response** (202 Accepted):
```json
{
  "execution_id": "exec_abc123",
  "agent_name": "data-analyzer",
  "status": "queued",
  "submitted_at": "2025-11-18T10:30:00Z",
  "estimated_start": "2025-11-18T10:30:05Z",
  "queue_position": 3,
  "trace_id": "trace_xyz789"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid task data
- `404 Not Found`: Agent not found
- `503 Service Unavailable`: Agent pool overloaded

#### Get Task Status

```http
GET /tasks/{execution_id}
```

Get current status of a submitted task.

**Path Parameters**:
- `execution_id` (string, required): Execution identifier

**Response** (200 OK):
```json
{
  "execution_id": "exec_abc123",
  "agent_name": "data-analyzer",
  "status": "running",
  "submitted_at": "2025-11-18T10:30:00Z",
  "started_at": "2025-11-18T10:30:05Z",
  "estimated_completion": "2025-11-18T10:32:00Z",
  "progress": 0.45,
  "trace_id": "trace_xyz789"
}
```

**Status Values**:
- `queued`: Waiting in queue
- `running`: Currently executing
- `completed`: Successfully finished
- `failed`: Execution failed
- `timeout`: Exceeded time limit
- `cancelled`: Manually cancelled

#### Cancel Task

```http
DELETE /tasks/{execution_id}
```

Cancel a queued or running task.

**Path Parameters**:
- `execution_id` (string, required): Execution identifier

**Response** (200 OK):
```json
{
  "execution_id": "exec_abc123",
  "cancelled": true,
  "previous_status": "running",
  "cancelled_at": "2025-11-18T10:31:00Z"
}
```

**Error Responses**:
- `404 Not Found`: Task not found
- `409 Conflict`: Task already completed

### Collaborative Tasks

#### Submit Collaborative Task

```http
POST /collaborative/tasks
```

Submit a complex task requiring multi-agent collaboration.

**Request Body**:
```json
{
  "coordinator_agent": "research-team",
  "task_description": "Research and create a comprehensive report on renewable energy trends in 2025",
  "max_agents": 5,
  "allow_human_clarification": true,
  "timeout_seconds": 600,
  "callback_url": "https://api.example.com/callbacks/collab-complete"
}
```

**Response** (202 Accepted):
```json
{
  "collaboration_id": "collab_abc123",
  "coordinator_agent": "research-team",
  "status": "planning",
  "submitted_at": "2025-11-18T10:30:00Z",
  "estimated_agents": 3,
  "trace_id": "trace_xyz789"
}
```

#### Get Collaboration Status

```http
GET /collaborative/tasks/{collaboration_id}
```

Get status of a collaborative task.

**Path Parameters**:
- `collaboration_id` (string, required): Collaboration identifier

**Response** (200 OK):
```json
{
  "collaboration_id": "collab_abc123",
  "coordinator_agent": "research-team",
  "status": "in_progress",
  "submitted_at": "2025-11-18T10:30:00Z",
  "started_at": "2025-11-18T10:30:10Z",
  "plan": {
    "steps": 5,
    "current_step": 2,
    "description": "Step 2: Data collection phase"
  },
  "participating_agents": [
    "research-team",
    "data-analyzer",
    "content-writer"
  ],
  "progress": 0.40,
  "estimated_completion": "2025-11-18T10:38:00Z"
}
```

### Metrics and Monitoring

#### Get Platform Metrics

```http
GET /metrics
```

Get overall platform metrics.

**Response** (200 OK):
```json
{
  "timestamp": "2025-11-18T10:30:00Z",
  "agents": {
    "total": 8,
    "healthy": 7,
    "unhealthy": 1
  },
  "tasks": {
    "queued": 12,
    "running": 23,
    "completed_today": 1542,
    "failed_today": 15
  },
  "performance": {
    "avg_task_duration_seconds": 4.5,
    "success_rate": 0.99,
    "throughput_per_minute": 125
  },
  "resources": {
    "cpu_percent": 45.2,
    "memory_percent": 62.1,
    "queue_depth": 12
  }
}
```

---

## SchedulerService API (Port 8004)

### Schedule Management

#### List All Schedules

```http
GET /schedules
```

List all registered schedules.

**Query Parameters**:
- `agent_name` (string, optional): Filter by agent
- `enabled` (boolean, optional): Filter by enabled status
- `schedule_type` (string, optional): cron or interval

**Response** (200 OK):
```json
{
  "schedules": [
    {
      "schedule_name": "daily-report",
      "agent_name": "daily-reporter",
      "schedule_type": "cron",
      "schedule_config": {
        "cron": "0 9 * * *",
        "timezone": "UTC"
      },
      "enabled": true,
      "next_run": "2025-11-19T09:00:00Z",
      "last_run": "2025-11-18T09:00:00Z",
      "last_status": "success",
      "run_count": 42
    }
  ],
  "total": 5
}
```

#### Get Schedule Details

```http
GET /schedules/{schedule_name}
```

Get detailed information about a specific schedule.

**Path Parameters**:
- `schedule_name` (string, required): Schedule identifier

**Response** (200 OK):
```json
{
  "schedule_name": "daily-report",
  "agent_name": "daily-reporter",
  "schedule_type": "cron",
  "schedule_config": {
    "cron": "0 9 * * *",
    "timezone": "UTC",
    "timeout_seconds": 600
  },
  "task_data": {
    "report_type": "daily",
    "recipients": ["team@example.com"]
  },
  "enabled": true,
  "created_at": "2025-11-01T00:00:00Z",
  "updated_at": "2025-11-18T10:00:00Z",
  "next_run": "2025-11-19T09:00:00Z",
  "last_run": "2025-11-18T09:00:00Z",
  "last_execution_id": "exec_xyz123",
  "last_status": "success",
  "run_count": 42,
  "success_count": 41,
  "failure_count": 1
}
```

#### Create Schedule

```http
POST /schedules
```

Create a new schedule for an agent.

**Request Body** (Cron):
```json
{
  "schedule_name": "weekly-summary",
  "agent_name": "report-generator",
  "schedule_type": "cron",
  "schedule_config": {
    "cron": "0 9 * * 0",
    "timezone": "America/New_York",
    "timeout_seconds": 600
  },
  "task_data": {
    "report_type": "weekly",
    "format": "pdf"
  },
  "enabled": true
}
```

**Request Body** (Interval):
```json
{
  "schedule_name": "health-check",
  "agent_name": "health-monitor",
  "schedule_type": "interval",
  "schedule_config": {
    "interval_seconds": 300,
    "timeout_seconds": 120
  },
  "task_data": {
    "checks": ["database", "cache", "queue"]
  },
  "enabled": true
}
```

**Response** (201 Created):
```json
{
  "schedule_name": "weekly-summary",
  "created": true,
  "next_run": "2025-11-24T09:00:00-05:00",
  "created_at": "2025-11-18T10:30:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid schedule configuration
- `404 Not Found`: Agent not found
- `409 Conflict`: Schedule name already exists

#### Update Schedule

```http
PUT /schedules/{schedule_name}
```

Update an existing schedule.

**Path Parameters**:
- `schedule_name` (string, required): Schedule identifier

**Request Body**:
```json
{
  "schedule_config": {
    "cron": "0 10 * * *",
    "timezone": "UTC"
  },
  "enabled": true
}
```

**Response** (200 OK):
```json
{
  "schedule_name": "daily-report",
  "updated": true,
  "next_run": "2025-11-19T10:00:00Z",
  "updated_at": "2025-11-18T10:30:00Z"
}
```

#### Delete Schedule

```http
DELETE /schedules/{schedule_name}
```

Delete a schedule.

**Path Parameters**:
- `schedule_name` (string, required): Schedule identifier

**Response** (204 No Content)

#### Enable/Disable Schedule

```http
PATCH /schedules/{schedule_name}/enabled
```

Enable or disable a schedule without deleting it.

**Path Parameters**:
- `schedule_name` (string, required): Schedule identifier

**Request Body**:
```json
{
  "enabled": false
}
```

**Response** (200 OK):
```json
{
  "schedule_name": "daily-report",
  "enabled": false,
  "updated_at": "2025-11-18T10:30:00Z"
}
```

#### Trigger Schedule Manually

```http
POST /schedules/{schedule_name}/trigger
```

Manually trigger a scheduled task (for testing).

**Path Parameters**:
- `schedule_name` (string, required): Schedule identifier

**Response** (202 Accepted):
```json
{
  "schedule_name": "daily-report",
  "execution_id": "exec_manual_abc123",
  "triggered_at": "2025-11-18T10:30:00Z",
  "status": "queued"
}
```

### Worker Management

#### Get Worker Status

```http
GET /workers
```

Get status of Celery workers.

**Response** (200 OK):
```json
{
  "workers": [
    {
      "hostname": "celery@scheduler-service-1",
      "status": "online",
      "active_tasks": 2,
      "processed_tasks": 1523,
      "pool_size": 2
    }
  ],
  "total_workers": 1,
  "total_active_tasks": 2
}
```

---

## SlackGateway API (Port 8005)

### Webhook Endpoints

#### Slack Events Webhook

```http
POST /slack/events
```

Receive events from Slack (configured in Slack App settings).

**Headers** (required):
```
X-Slack-Request-Timestamp: 1605139200
X-Slack-Signature: v0=a2114d57b48eac39b9ad189dd8316235a7b4a8d21a10bd27519666489c69b503
Content-Type: application/json
```

**Request Body** (URL Verification):
```json
{
  "type": "url_verification",
  "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P"
}
```

**Response** (200 OK):
```json
{
  "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P"
}
```

**Request Body** (Event):
```json
{
  "type": "event_callback",
  "event": {
    "type": "message",
    "channel": "C123456",
    "user": "U789012",
    "text": "help",
    "ts": "1605139200.000100"
  }
}
```

**Response** (200 OK):
```json
{
  "ok": true
}
```

#### Slack Interactive Components

```http
POST /slack/interactive
```

Handle Slack interactive components (buttons, menus, etc.).

**Headers** (required):
```
X-Slack-Request-Timestamp: 1605139200
X-Slack-Signature: v0=...
Content-Type: application/json
```

**Request Body**:
```json
{
  "type": "block_actions",
  "user": {
    "id": "U789012",
    "name": "user"
  },
  "actions": [
    {
      "action_id": "approve_action",
      "value": "approve"
    }
  ],
  "response_url": "https://hooks.slack.com/actions/..."
}
```

**Response** (200 OK):
```json
{
  "ok": true
}
```

### Message Sending

#### Send Message

```http
POST /slack/send-message
```

Send a message to a Slack channel.

**Request Body**:
```json
{
  "channel": "#general",
  "text": "Task completed successfully!",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Task Results*\nStatus: ✅ Complete"
      }
    }
  ],
  "thread_ts": "1605139200.000100"
}
```

**Response** (200 OK):
```json
{
  "ok": true,
  "channel": "C123456",
  "ts": "1605139210.000200",
  "message": {
    "text": "Task completed successfully!",
    "user": "UBOT123"
  }
}
```

**Error Responses**:
- `400 Bad Request`: Missing required fields
- `401 Unauthorized`: Invalid Slack token
- `404 Not Found`: Channel not found
- `429 Too Many Requests`: Rate limit exceeded

#### Update Message

```http
PUT /slack/messages/{ts}
```

Update an existing message.

**Path Parameters**:
- `ts` (string, required): Message timestamp

**Request Body**:
```json
{
  "channel": "C123456",
  "text": "Updated message text",
  "blocks": [...]
}
```

**Response** (200 OK):
```json
{
  "ok": true,
  "channel": "C123456",
  "ts": "1605139200.000100",
  "text": "Updated message text"
}
```

#### Delete Message

```http
DELETE /slack/messages/{ts}
```

Delete a message.

**Path Parameters**:
- `ts` (string, required): Message timestamp

**Query Parameters**:
- `channel` (string, required): Channel ID

**Response** (204 No Content)

---

## Error Codes

### Standard HTTP Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 202 | Accepted | Request accepted for processing |
| 204 | No Content | Request successful, no content to return |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict (duplicate name, etc.) |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |
| 502 | Bad Gateway | Upstream service error |
| 503 | Service Unavailable | Service temporarily unavailable |
| 504 | Gateway Timeout | Upstream service timeout |

### Error Response Format

All error responses follow this format:

```json
{
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Agent 'unknown-agent' not found",
    "details": {
      "agent_name": "unknown-agent",
      "available_agents": ["agent1", "agent2"]
    },
    "timestamp": "2025-11-18T10:30:00Z",
    "trace_id": "trace_abc123"
  }
}
```

### Error Codes Reference

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AGENT_NOT_FOUND` | 404 | Agent does not exist |
| `INVALID_CONFIG` | 400 | Invalid agent configuration |
| `INVALID_TASK_DATA` | 400 | Invalid task data format |
| `EXECUTION_NOT_FOUND` | 404 | Execution ID not found |
| `SCHEDULE_NOT_FOUND` | 404 | Schedule not found |
| `SCHEDULE_CONFLICT` | 409 | Schedule name already exists |
| `INVALID_CRON` | 400 | Invalid cron expression |
| `AGENT_UNHEALTHY` | 503 | Agent is not healthy |
| `QUEUE_FULL` | 503 | Task queue is full |
| `TIMEOUT` | 504 | Request timeout |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `AUTH_FAILED` | 401 | Authentication failed |
| `SIGNATURE_INVALID` | 401 | Slack signature verification failed |
| `DATABASE_ERROR` | 500 | Database operation failed |
| `CACHE_ERROR` | 500 | Cache operation failed |

---

## Rate Limiting

### Rate Limit Headers

All responses include rate limit headers:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1605139260
```

### Rate Limit Response

When rate limit is exceeded:

**Status**: 429 Too Many Requests

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 23 seconds.",
    "details": {
      "limit": 60,
      "remaining": 0,
      "reset_at": "2025-11-18T10:31:00Z",
      "retry_after_seconds": 23
    }
  }
}
```

### Rate Limit Configuration

Configure rate limits in `.env`:

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

---

## WebSocket Events

### Real-time Task Updates (Future Feature)

Connect to WebSocket for real-time task status updates:

```javascript
const ws = new WebSocket('ws://localhost:8003/ws/tasks/exec_abc123');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Task update:', update);
};
```

**Event Format**:
```json
{
  "event_type": "task_status_update",
  "execution_id": "exec_abc123",
  "status": "running",
  "progress": 0.65,
  "timestamp": "2025-11-18T10:30:15Z"
}
```

---

## OpenAPI/Swagger Documentation

### Interactive API Documentation

Each service exposes interactive Swagger UI documentation:

| Service | Swagger UI URL |
|---------|----------------|
| StateManager | `http://localhost:8001/docs` |
| ConfigurationService | `http://localhost:8002/docs` |
| AgentOrchestrator | `http://localhost:8003/docs` |
| SchedulerService | `http://localhost:8004/docs` |
| SlackGateway | `http://localhost:8005/docs` |

### OpenAPI Schema

Download OpenAPI 3.0 schema:

```bash
curl http://localhost:8001/openapi.json > statemanager-api.json
```

---

## Code Examples

### Python

```python
import requests

# Submit task
response = requests.post(
    'http://localhost:8003/tasks',
    json={
        'agent_name': 'data-analyzer',
        'task_data': {
            'action': 'analyze',
            'dataset_id': 'ds_123'
        }
    },
    headers={'X-API-Key': 'your-api-key'}
)

execution_id = response.json()['execution_id']

# Poll for completion
import time
while True:
    status_response = requests.get(
        f'http://localhost:8003/tasks/{execution_id}',
        headers={'X-API-Key': 'your-api-key'}
    )
    status = status_response.json()['status']

    if status in ['completed', 'failed']:
        break

    time.sleep(2)

print(f'Task {status}')
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

async function submitTask() {
  // Submit task
  const response = await axios.post(
    'http://localhost:8003/tasks',
    {
      agent_name: 'data-analyzer',
      task_data: {
        action: 'analyze',
        dataset_id: 'ds_123'
      }
    },
    {
      headers: { 'X-API-Key': 'your-api-key' }
    }
  );

  const executionId = response.data.execution_id;

  // Poll for completion
  while (true) {
    const statusResponse = await axios.get(
      `http://localhost:8003/tasks/${executionId}`,
      { headers: { 'X-API-Key': 'your-api-key' } }
    );

    const status = statusResponse.data.status;

    if (status === 'completed' || status === 'failed') {
      break;
    }

    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  console.log(`Task ${status}`);
}
```

### cURL

```bash
# Submit task
curl -X POST http://localhost:8003/tasks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "agent_name": "data-analyzer",
    "task_data": {
      "action": "analyze",
      "dataset_id": "ds_123"
    }
  }'

# Get task status
curl http://localhost:8003/tasks/exec_abc123 \
  -H "X-API-Key: your-api-key"
```

---

## Further Reading

- [Operations Guide](OPERATIONS_GUIDE.md) - Deployment and operations
- [Agent Development Guide](AGENT_DEVELOPMENT_GUIDE.md) - Creating agents
- [Configuration Reference](CONFIGURATION_REFERENCE.md) - Configuration options
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) - Common issues and solutions

---

**Last Updated**: 2025-11-18
**Version**: 1.0
**OpenAPI Version**: 3.0.0
