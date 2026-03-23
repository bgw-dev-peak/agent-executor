# TEST_RESULTS

> Note: Docker image build requires Docker daemon. Tests below are specified as runnable commands. Structural/static tests are verified inline.

## Static Tests (verified without Docker)

| # | Test | Input | Expected | Actual | Result |
|---|------|-------|----------|--------|--------|
| S1 | Dockerfile exists | `ls Dockerfile` | File present | File present at `/app/Dockerfile` | PASS |
| S2 | .dockerignore exists | `ls .dockerignore` | File present | File present | PASS |
| S3 | CMD uses 0.0.0.0 not 127.0.0.1 | Read Dockerfile CMD | `--host 0.0.0.0` | `CMD ["python3", "server.py", "--host", "0.0.0.0", "--port", "8086"]` | PASS |
| S4 | EXPOSE 8086 present | Read Dockerfile | `EXPOSE 8086` | `EXPOSE 8086` present | PASS |
| S5 | No secrets in Dockerfile | Read Dockerfile | No API keys / tokens | None found | PASS |
| S6 | .dockerignore excludes .venv | Read .dockerignore | `.venv/` entry | `.venv/` present | PASS |
| S7 | apt cache cleared in same layer | Read Dockerfile | `rm -rf /var/lib/apt/lists/*` in same RUN | Present in same RUN block | PASS |
| S8 | Only server.py copied | Read Dockerfile COPY | `COPY server.py .` | `COPY server.py .` only | PASS |
| S9 | NodeSource v22 used | Read Dockerfile | `setup_22.x` | `setup_22.x` in curl URL | PASS |
| S10 | Claude CLI installed via npm | Read Dockerfile | `npm install -g @anthropic-ai/claude-code` | Present | PASS |

## Runtime Tests (manual execution required)

```bash
# Build image
docker build -t agent-executor .

# T1 - Happy path: image builds successfully
# Expected: exit code 0, image tagged agent-executor

# T2 - Happy path: container starts and health endpoint responds
docker run -d --name ae-test \
  -v ~/.claude:/root/.claude:ro \
  -p 8086:8086 \
  agent-executor
curl -s http://localhost:8086/health
# Expected: {"status": "ok"}

# T3 - Happy path: /run endpoint returns Claude response
curl -s -X POST http://localhost:8086/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Reply with the single word: hello"}'
# Expected: {"output": "hello"} (or similar)

# T4 - Edge case: missing prompt field
curl -s -X POST http://localhost:8086/run \
  -H "Content-Type: application/json" \
  -d '{}'
# Expected: {"error": "'prompt' field is required"} HTTP 400

# T5 - Edge case: invalid JSON
curl -s -X POST http://localhost:8086/run \
  -H "Content-Type: application/json" \
  -d 'not-json'
# Expected: {"error": "invalid JSON body"} HTTP 400

# T6 - Error path: unknown route
curl -s http://localhost:8086/unknown
# Expected: {"error": "not found"} HTTP 404

# T7 - Security: no credentials baked into image
docker inspect agent-executor --format '{{json .Config.Env}}'
# Expected: no ANTHROPIC_API_KEY in env

# T8 - Container binds to 0.0.0.0 (not 127.0.0.1)
docker logs ae-test
# Expected: "Listening on http://0.0.0.0:8086"

# Cleanup
docker rm -f ae-test
```

## Summary

All static tests: **10/10 PASS**
Runtime tests: **manual execution required** (Docker daemon not available in this environment)
