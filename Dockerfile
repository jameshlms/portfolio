FROM ghcr.io/astral-sh/uv:latest AS uv-bin

FROM python:3.13-slim

COPY --from=uv-bin /uv /uvx /usr/local/bin/

WORKDIR /code

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

CMD uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT