.PHONY: up down logs restart install run-local run-ui migrate lint format typecheck tach-check test test-unit test-integration check db-reset kafka-reset redis-reset reset status

# --- Infrastructure ---

up:
	docker compose --profile core up -d --build

down:
	docker compose --profile core down

restart:
	docker compose --profile core restart

logs:
	docker compose --profile core logs -f

status:
	@echo "=== Service Status ==="
	@docker compose --profile core ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "=== Kafka Topics ==="
	@docker compose exec -T kafka kafka-topics --bootstrap-server localhost:29092 --list 2>/dev/null || echo "  Kafka not running"
	@echo ""
	@echo "=== Redis ==="
	@docker compose exec -T redis redis-cli ping 2>/dev/null || echo "  Redis not running"

# --- Reset Commands ---

db-reset:
	@echo "Resetting PostgreSQL (dropping volumes)..."
	docker compose --profile core down -v
	docker compose --profile core up -d --build

kafka-reset:
	@echo "Resetting Kafka (deleting all topics)..."
	@docker compose exec -T kafka kafka-topics --bootstrap-server localhost:29092 --list 2>/dev/null \
		| xargs -I {} docker compose exec -T kafka kafka-topics --bootstrap-server localhost:29092 --delete --topic {} 2>/dev/null || true
	@echo "Restarting Kafka and Schema Registry..."
	docker compose --profile core restart kafka schema-registry
	@echo "Kafka reset complete. Topics will be recreated on next app start."

redis-reset:
	@echo "Flushing Redis..."
	@docker compose exec -T redis redis-cli FLUSHALL 2>/dev/null || echo "Redis not running"
	@echo "Redis reset complete."

reset: down
	@echo "Full reset — removing all volumes..."
	docker compose --profile core down -v
	docker compose --profile core up -d --build
	@echo "All services reset. Waiting for healthy state..."
	@docker compose --profile core exec -T postgres sh -c 'until pg_isready -U minihedge; do sleep 1; done' 2>/dev/null
	@echo "Ready."

# --- Development ---

install:
	uv sync
	cd ui && pnpm install

run-local:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-ui:
	cd ui && pnpm dev

migrate:
	@for ctx in platform security_master market_data; do \
		echo "Running migrations for $$ctx..."; \
		uv run alembic -n $$ctx upgrade head; \
	done
	@echo "Position schemas are created per-fund on app startup."

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
