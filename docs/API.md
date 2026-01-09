# API Reference

AgentLens Orchestrator exposes a REST API and WebSocket endpoint for real-time agent events.

**Base URL:** `http://localhost:8001`

---

## Endpoints

### `POST /orchestrate`

Execute a coding task through the multi-agent pipeline.

**Request Body:**
```json
{
  "task": "Create a Python function that calculates fibonacci numbers",
  "max_retries": 3
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `task` | string | ✅ | - | The coding task to execute (min 1 char) |
| `max_retries` | integer | ❌ | 3 | Max retry attempts on failure (0-10) |

**Response:**
```json
{
  "success": true,
  "task": "Create a Python function...",
  "code": "def fibonacci(n):\n    ...",
  "file_path": "/workspace/fibonacci.py",
  "execution_output": "Fibonacci of 10: 55",
  "retries": 0,
  "history": [...],
  "files": {
    "fibonacci.py": "def fibonacci(n):..."
  },
  "preview_url": "/preview/index.html"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether execution completed successfully |
| `task` | string | Original task |
| `code` | string | Generated code |
| `file_path` | string | Path where code was written |
| `execution_output` | string | stdout/stderr from execution |
| `retries` | integer | Number of retry attempts made |
| `history` | array | Agent execution history |
| `files` | object | Map of all generated files |
| `preview_url` | string | URL for iframe preview (if HTML) |

---

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "orchestrator",
  "version": "0.1.0"
}
```

---

### `GET /metrics`

Prometheus metrics endpoint.

**Response:** Prometheus text format

```
# HELP orchestration_requests_total Total orchestration requests
# TYPE orchestration_requests_total counter
orchestration_requests_total 42.0
...
```

---

## WebSocket

### `WS /ws/events`

Real-time agent event stream.

**Connection:** `ws://localhost:8001/ws/events`

**Event Format:**
```json
{
  "type": "agent_start",
  "agent": "coder",
  "timestamp": 1704672000.123,
  "data": {
    "task": "Create fibonacci function"
  }
}
```

**Event Types:**

| Type | Agent | Data Fields | Description |
|------|-------|-------------|-------------|
| `agent_start` | any | `task` | Agent began processing |
| `agent_end` | any | `success`, `duration`, `tokens`, `latency` | Agent finished |
| `token` | any | `token` | Token generated (streaming) |
| `code_written` | coder | `file_path`, `code` | Code written to workspace |
| `file_created` | coder | `file_path`, `content`, `size` | New file created |
| `execution` | executor | `success`, `output`, `exit_code` | Code execution result |
| `error` | any | `error` | Error occurred |
| `complete` | orchestrator | - | Task completed |
| `workspace_reset` | orchestrator | - | Workspace cleared |

---

## Error Handling

All endpoints return standard HTTP status codes:

| Code | Description |
|------|-------------|
| 200 | Success |
| 422 | Validation error (invalid request body) |
| 500 | Internal server error |

Errors include a JSON body:
```json
{
  "detail": "Error description"
}
```
