# agent-executor

A lightweight HTTP service that wraps the [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) and exposes it over HTTP. Send a prompt via POST, get Claude's response back — no API key management required.

**Primary use case:** Automation and scripting — trigger Claude from CI pipelines, cron jobs, shell scripts, or any tool that can make an HTTP request.

---

## Features

- **Zero dependencies** — built on Python's standard library (`http.server`, `pty`, `subprocess`), no `pip install` required
- **Synchronous responses** — send a request, wait, get the full response back (ideal for scripting)
- **PTY-based execution** — uses a pseudo-terminal to correctly capture Claude CLI output
- **ANSI output cleaning** — strips all terminal escape sequences from responses, returning clean plain text
- **Timeout protection** — requests timeout after 300 seconds, server recovers cleanly
- **Structured error responses** — all errors return JSON with a consistent `{"error": "..."}` shape
- **Safe by default** — binds to `127.0.0.1` only; prompts are passed as argument lists (no shell injection)
- **Configurable host/port** — override via CLI flags

---

## Requirements

- Python 3.7+
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated (`claude` must be in your `PATH`)
- macOS or Linux (uses `pty` module — not available on Windows)

---

## Usage

### Start the server

```bash
python3 server.py
# Listening on http://127.0.0.1:8086
#   POST /run    {"prompt": "..."}
#   GET  /health
```

Custom host and port:

```bash
python3 server.py --host 0.0.0.0 --port 9000
```

### API

#### `POST /run`

Run a prompt through Claude and get the response.

**Request:**
```bash
curl -s -X POST http://127.0.0.1:8086/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2 + 2?"}'
```

**Response (200):**
```json
{"output": "4"}
```

**Error responses:**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Missing or empty `prompt` | `{"error": "'prompt' field is required"}` |
| 400 | Invalid JSON body | `{"error": "invalid JSON body"}` |
| 404 | Unknown route | `{"error": "not found"}` |
| 500 | Claude CLI not found in PATH | `{"error": "claude CLI not found in PATH"}` |
| 500 | Claude exited with non-zero code | `{"error": "<stderr output>"}` |
| 504 | Request timed out (> 300s) | `{"error": "claude timed out after 300s"}` |

#### `GET /health`

Health check endpoint.

```bash
curl http://127.0.0.1:8086/health
# {"status": "ok"}
```

---

## Examples

### Shell script

```bash
RESPONSE=$(curl -s -X POST http://127.0.0.1:8086/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize this in one sentence: '"$TEXT"'"}')

echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['output'])"
```

### Python

```python
import httpx

response = httpx.post("http://127.0.0.1:8086/run", json={"prompt": "Say hello"})
print(response.json()["output"])
```

### CI pipeline (GitHub Actions)

```yaml
- name: Ask Claude
  run: |
    curl -s -X POST http://127.0.0.1:8086/run \
      -H "Content-Type: application/json" \
      -d '{"prompt": "Review this diff for security issues"}' \
      | jq -r .output
```

---

## Configuration

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Host to bind to |
| `--port` | `8086` | Port to listen on |

The request timeout is hardcoded to **300 seconds** and can be changed by editing the `TIMEOUT` constant in `server.py`.

---

## ⚠️ Notices

**Authentication:** The server has **no authentication**. It is designed for trusted local or internal network use only. Do not expose it to the public internet without adding an authentication layer (e.g., a reverse proxy with basic auth or mTLS).

**Permissions:** The server runs Claude with `--dangerously-skip-permissions`. This means Claude will execute without interactive permission prompts. Only use this in environments where you trust the prompts being sent.

**Windows:** The `pty` module used to capture Claude CLI output is **not available on Windows**. This service runs on macOS and Linux only.

**Concurrency:** The server handles one request at a time (no thread pool). For concurrent workloads, run multiple instances behind a load balancer or refactor to use `ThreadingMixIn`.

**Prompt injection:** Prompts are passed directly to Claude as-is. If your service accepts user-supplied input, sanitize or restrict prompts before forwarding them.

---

## Project Structure

```
agent-executor/
├── server.py               # HTTP server + Claude CLI runner
├── docs/
│   ├── brainstorms/
│   │   └── 2026-03-22-claude-http-service-brainstorm.md
│   └── workflow-roles.md   # Design decisions and workflow roles
└── README.md
```

---

## How It Works

Claude CLI requires a TTY (pseudo-terminal) to produce output — it silently produces nothing when stdout is a plain pipe. `server.py` solves this with `pty.openpty()`:

1. A PTY master/slave pair is created
2. Claude is launched with the slave end as its stdout/stderr
3. The server reads from the master end using `select()` until EOF
4. Raw output is decoded and stripped of ANSI/VT100 escape sequences
5. Clean text is returned as JSON

---

## License

MIT
