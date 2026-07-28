FROM --platform=linux/arm64 python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    tar \
    procps \
    libe2p2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
    
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /workspace
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project || true

COPY . .
RUN uv sync --frozen