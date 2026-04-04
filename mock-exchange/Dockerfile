FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN useradd -m -r -s /bin/false appuser

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || uv sync --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8100

CMD ["uv", "run", "uvicorn", "mock_exchange.main:app", "--host", "0.0.0.0", "--port", "8100"]
