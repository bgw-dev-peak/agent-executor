# Brainstorm: Claude CLI HTTP Service

**Date:** 2026-03-22
**Status:** Draft

---

## What We're Building

A lightweight Python (FastAPI) web service that wraps the `claude` CLI and exposes it over HTTP. Callers POST a prompt, the service shells out to `claude` as a subprocess, waits for the full response, and returns it in the HTTP response body.

**Primary use case:** Automation and scripting — trigger Claude from CI pipelines, cron jobs, shell scripts, or any tool that can make an HTTP request.

---

## Why This Approach

**FastAPI + synchronous subprocess (chosen over async job queue and direct API)**

- Synchronous (blocking) response is the simplest mental model for scripting: send a request, get a response. No job IDs, no polling.
- Shelling out to `claude` CLI reuses existing local auth/config — no API key management in the service itself.
- FastAPI handles the async I/O gracefully even with blocking subprocesses, and gives free `/docs` UI.
- YAGNI: async job queue adds complexity that isn't needed for automation scripts.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | FastAPI | Async-native, auto-docs, minimal boilerplate |
| Execution | subprocess (`claude -p "..."`) | Reuse existing CLI auth and config |
| Response style | Synchronous (blocking) | Simpler for scripting; client just waits |
| Language | Python | Consistent with project (`agent-executor`) |
| Auth | None initially | Trusted local/internal network assumed |

---

## API Design (sketch)

```
POST /run
Body: { "prompt": "your prompt here" }

Response 200: { "output": "Claude's response text" }
Response 500: { "error": "stderr output or timeout message" }

GET /health
Response 200: { "status": "ok" }
```

---

## Open Questions

_None._

---

## Resolved Questions

| Question | Decision |
|----------|----------|
| Response mode | Synchronous — wait for full output |
| Stack | Python + FastAPI |
| Subprocess vs direct API | Shell out to `claude` CLI |
| Primary use case | Automation / scripting |
| Extra CLI flags | No — prompt only, keep API surface minimal |
| Subprocess timeout | 300 seconds (5 minutes) |
| Authentication | None — trusted local/internal network |

---

## Out of Scope (for now)

- Streaming / SSE
- Async job queue with polling
- Authentication
- Persistent job storage
- Docker packaging
