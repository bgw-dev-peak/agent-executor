# DESIGN

## Decision Table

| Decision | Options | Chosen | Rationale |
|----------|---------|--------|-----------|
| Base image | `python:3.13-slim` vs `node:22-slim` | `python:3.13-slim` | App is primarily Python; add Node.js on top is simpler than adding Python to a Node image |
| Node.js install | NodeSource script vs `apt nodejs` | NodeSource (v22.x) | `apt nodejs` is typically too old for modern npm packages |
| Claude CLI install | `npm install -g` vs pre-built binary | `npm install -g @anthropic-ai/claude-code` | Official distribution channel |
| Auth credentials | Volume mount vs bake-in | Volume mount at runtime | Never bake credentials into an image |
| Host binding | Default `127.0.0.1` | `0.0.0.0` via CMD flag | `127.0.0.1` is loopback-only; Docker bridge traffic arrives on eth0 |
| .dockerignore | Yes | Yes | Exclude `.venv`, `.git`, docs to keep image small |

## Architecture Diagram

```
Host machine
│
├── ~/.claude/   ──(volume mount)──► /root/.claude/  (auth token)
│
└── docker run -p 8086:8086
        │
        ▼
  ┌─────────────────────────────────────┐
  │  Docker Container                   │
  │                                     │
  │  /app/server.py                     │
  │    └─ HTTPServer (0.0.0.0:8086)     │
  │         │                           │
  │         └─ subprocess: claude -p    │
  │              (via PTY)              │
  │                                     │
  │  /usr/local/bin/claude  (npm global)│
  └─────────────────────────────────────┘
        │
        ▼
  Client: POST http://localhost:8086/run
```

## File Contract

### `Dockerfile`
```
FROM python:3.13-slim
→ Install curl, ca-certificates
→ Add NodeSource repo, install nodejs
→ npm install -g @anthropic-ai/claude-code
→ WORKDIR /app
→ COPY server.py .
→ EXPOSE 8086
→ CMD ["python3", "server.py", "--host", "0.0.0.0", "--port", "8086"]
```

### `.dockerignore`
Excludes: `.venv/`, `.git/`, `docs/`, `*.md`, `REQUIREMENTS.md`, `DESIGN.md`, `IMPL_CHECKLIST.md`, `TEST_RESULTS.md`, `VALIDATION_REPORT.md`

## Error Mapping

| Condition | Behaviour |
|-----------|-----------|
| `claude` not in PATH | HTTP 500 `{"error": "claude CLI not found in PATH"}` (existing server.py logic) |
| Auth credentials not mounted | `claude` exits non-zero → HTTP 500 with claude's error message |
| Container port not published | Connection refused on host — no change to server behaviour |
| Server bound to wrong host | Requests time out — solved by `--host 0.0.0.0` in CMD |

## Security Notes
- No credentials in the image; auth config injected at runtime via `-v ~/.claude:/root/.claude:ro`
- `ANTHROPIC_API_KEY` can alternatively be passed via `-e ANTHROPIC_API_KEY=...`
- Image runs as root (acceptable for single-purpose internal tooling; can be hardened with `USER` directive if needed)
- `.dockerignore` prevents accidentally copying `.env` or venv into the image
