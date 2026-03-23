# IMPL_CHECKLIST

## Engineer Checklist

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Follows DESIGN.md exactly — no extra features | ✅ | Dockerfile matches design spec precisely |
| 2 | No shell string interpolation in subprocess calls | ✅ | Dockerfile uses `RUN` with explicit argument arrays where applicable; server.py unchanged |
| 3 | Resources cleaned up properly | ✅ | `apt-get` caches removed in same RUN layer (`rm -rf /var/lib/apt/lists/*`) |
| 4 | No hardcoded credentials or secrets | ✅ | Auth supplied at runtime via volume mount or env var — not baked in |
| 5 | Base image is minimal | ✅ | `python:3.13-slim` (Debian slim, no extras) |
| 6 | Node.js from official NodeSource v22.x | ✅ | Ensures `npm` is current enough for `@anthropic-ai/claude-code` |
| 7 | Claude CLI installed globally | ✅ | `npm install -g @anthropic-ai/claude-code` |
| 8 | Server bound to 0.0.0.0 in CMD | ✅ | `["python3", "server.py", "--host", "0.0.0.0", "--port", "8086"]` |
| 9 | Port 8086 exposed | ✅ | `EXPOSE 8086` |
| 10 | .dockerignore excludes venv, git, docs, delivery docs | ✅ | Prevents bloat and accidental credential inclusion |
| 11 | Only `server.py` copied into image | ✅ | `COPY server.py .` |
| 12 | WORKDIR set | ✅ | `WORKDIR /app` |
