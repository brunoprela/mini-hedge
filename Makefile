.PHONY: up down install run migrate seed lint format typecheck tach-check test test-unit test-integration check

# --- Infrastructure ---

up:
	docker compose --profile core up -d

down:
	docker compose --profile core down

# --- Development ---

install:
	uv sync

run:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	@for ctx in platform security_master market_data positions; do \
		echo "Running migrations for $$ctx..."; \
		uv run alembic -n $$ctx upgrade head; \
	done

seed:
	uv run python -m app.seed

# --- Quality ---

lint:
	uv run ruff check app/ tests/
	uv run ruff format --check app/ tests/

format:
	uv run ruff check --fix app/ tests/
	uv run ruff format app/ tests/

typecheck:
	uv run mypy app/

tach-check:
	uv run tach check

test:
	uv run pytest

test-unit:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

check: lint typecheck tach-check test
