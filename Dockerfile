FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh

RUN mkdir -p data

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
