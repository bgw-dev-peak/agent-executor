# REQUIREMENTS

## Raw Requirement
Add a Dockerfile so the agent-executor service can be built as a Docker image and run as a container.

## Core Problem
The service (`server.py`) depends on:
1. Python 3 (standard library only — no pip packages)
2. The `claude` CLI binary (installed via npm / Node.js)
3. Claude CLI authentication config (stored in `~/.claude/` on the host)
4. The `pty` module (Linux standard library — works in containers)

The default host `127.0.0.1` won't route traffic from outside the container; it must be overridden to `0.0.0.0`.

## Constraints
- Linux base image (pty works on Linux, not Windows)
- Python ≥ 3.7 (stdlib only — no pip install needed)
- Node.js required to install `@anthropic-ai/claude-code` via npm
- Claude CLI authentication credentials supplied at runtime via volume mount or env var
- Server must bind to `0.0.0.0` inside the container
- Default exposed port: **8086**
- No extra Python dependencies to install

## Out of Scope
- docker-compose file
- Multi-stage build optimizations
- Reverse proxy / TLS termination
- Authentication layer on the HTTP API

## Resolved Questions
- **How is claude CLI installed?** Via `npm install -g @anthropic-ai/claude-code`
- **How are credentials provided?** Mount host `~/.claude` into container at `/root/.claude`; alternatively pass `ANTHROPIC_API_KEY` env var
- **Which Python version?** Match host venv: Python 3.13 (3.13-slim image)
