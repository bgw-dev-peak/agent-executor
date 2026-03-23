FROM python:3.13-slim

# Install curl + ca-certificates, then add NodeSource repo and install Node.js
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

COPY server.py .

EXPOSE 8086

# Bind to 0.0.0.0 so Docker bridge traffic reaches the server
CMD ["python3", "server.py", "--host", "0.0.0.0", "--port", "8086"]
