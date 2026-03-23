#!/usr/bin/env python3
"""
Claude CLI HTTP wrapper service.

Usage:
    python3 server.py [--port PORT] [--host HOST]

POST /run    {"prompt": "your question"}  → {"output": "..."}
GET  /health                              → {"status": "ok"}
"""

import json
import os
import pty
import re
import select
import subprocess
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer

TIMEOUT = 300  # seconds

# Strip ANSI/VT100 escape sequences (OSC must come before single-char catch-all)
_ANSI_RE = re.compile(r"\x1b(?:\][^\x07\x1b]*[\x07\x1b]|\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])")


def run_claude(prompt: str) -> tuple[int, str]:
    """
    Run `claude -p <prompt>` inside a PTY (required for claude to produce output).
    Returns (returncode, output_text).
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    master_fd, slave_fd = pty.openpty()
    try:
        proc = subprocess.Popen(
            ["claude", "-p", prompt, "--dangerously-skip-permissions"],
            stdout=slave_fd,
            stderr=slave_fd,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        os.close(slave_fd)

        chunks: list[bytes] = []
        import time
        deadline = time.time() + TIMEOUT

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                proc.kill()
                proc.wait()
                return -1, f"claude timed out after {TIMEOUT}s"

            r, _, _ = select.select([master_fd], [], [], min(remaining, 1.0))
            if r:
                try:
                    chunk = os.read(master_fd, 4096)
                    if chunk:
                        chunks.append(chunk)
                    else:
                        break  # EOF
                except OSError:
                    break  # EOF / closed

            if proc.poll() is not None:
                # Drain any remaining output
                while True:
                    r, _, _ = select.select([master_fd], [], [], 0.05)
                    if not r:
                        break
                    try:
                        chunk = os.read(master_fd, 4096)
                        if chunk:
                            chunks.append(chunk)
                    except OSError:
                        break
                break

        rc = proc.wait()
        raw = b"".join(chunks).decode(errors="replace")
        clean = _ANSI_RE.sub("", raw).replace("\r\n", "\n").replace("\r", "\n").strip()
        return rc, clean

    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}", flush=True)

    def send_json(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/run":
            self.send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self.send_json(400, {"error": "invalid JSON body"})
            return

        prompt = body.get("prompt", "").strip()
        if not prompt:
            self.send_json(400, {"error": "'prompt' field is required"})
            return

        try:
            rc, output = run_claude(prompt)
        except FileNotFoundError:
            self.send_json(500, {"error": "claude CLI not found in PATH"})
            return

        if "timed out" in output and rc == -1:
            self.send_json(504, {"error": output})
            return

        if rc != 0:
            self.send_json(500, {"error": output or f"claude exited with code {rc}"})
            return

        self.send_json(200, {"output": output})


def main():
    parser = argparse.ArgumentParser(description="Claude CLI HTTP wrapper")
    parser.add_argument("--port", type=int, default=8086)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    print(f"Listening on http://{args.host}:{args.port}", flush=True)
    print(f'  POST /run    {{"prompt": "..."}}', flush=True)
    print(f"  GET  /health", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
