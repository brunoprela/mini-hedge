.PHONY: up down logs restart install run-local run-ui run-ops-ui migrate lint format typecheck tach-check test test-unit test-integration check db-reset kafka-reset redis-reset reset status mock-exchange-up mock-exchange-down mock-exchange-logs mock-exchange-status up-all down-all seed seed-trades seed-all

# --- Platform Infrastructure ---

up:
	docker compose --profile core up -d --build

down:
	docker compose --profile core down

restart:
	docker compose --profile core restart

logs:
	docker compose --profile core logs -f

status:
	@echo "=== Platform Services ==="
	@docker compose --profile core ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "=== Kafka Topics ==="
	@docker compose exec -T kafka kafka-topics --bootstrap-server localhost:29092 --list 2>/dev/null || echo "  Kafka not running"
	@echo ""
	@echo "=== Redis ==="
	@docker compose exec -T redis redis-cli ping 2>/dev/null || echo "  Redis not running"

# --- Mock Exchange (independent service) ---

mock-exchange-up:
	cd mock-exchange && docker compose up -d --build

mock-exchange-down:
	cd mock-exchange && docker compose down

mock-exchange-logs:
	cd mock-exchange && docker compose logs -f

mock-exchange-status:
	@echo "=== Mock Exchange ==="
	@cd mock-exchange && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@curl -sf http://localhost:8100/api/v1/scenarios/state 2>/dev/null | python3 -m json.tool || echo "  Mock Exchange not running"

# --- Full Stack (platform + mock-exchange, all in core profile) ---

up-all: up
	@echo "Waiting for platform..."
	@until curl -sf http://localhost:8000/health > /dev/null 2>&1; do sleep 2; done
	@echo "All services running."
	@echo "  Platform:       http://localhost:8000"
	@echo "  UI:             http://localhost:3000"
	@echo "  Mock Exchange:  http://localhost:8100"
	@echo "  Mock Exchange Kafka: localhost:9192"

down-all: down

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
	@echo "Starting all services..."
	docker compose --profile core up -d --build
	@echo "Waiting for Postgres..."
	@docker compose --profile core exec -T postgres sh -c 'until pg_isready -U minihedge; do sleep 1; done' 2>/dev/null
	@echo "Waiting for platform..."
	@until curl -sf http://localhost:8000/health > /dev/null 2>&1; do sleep 2; done
	@echo "Running migrations..."
	@$(MAKE) migrate
	@echo "Seeding data..."
	@$(MAKE) seed
	@echo "Ready — all services running with seed data."
	@echo "  Platform:       http://localhost:8000"
	@echo "  Mock Exchange:  http://localhost:8100"

# --- Development ---

install:
	uv sync
	cd ui && pnpm install
	cd ops-ui && pnpm install
	cd mock-exchange && uv sync

run-local:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-ui:
	cd ui && pnpm dev

run-ops-ui:
	cd ops-ui && pnpm dev

migrate:
	@for ctx in platform security_master market_data; do \
		echo "Running migrations for $$ctx..."; \
		uv run alembic -n $$ctx upgrade head; \
	done
	@echo "Position schemas are created per-fund on app startup."

seed:
	uv run python -m app.seed

seed-trades:
	uv run python -m app.seed_trades

seed-all: seed seed-trades

# --- Quality ---

lint:
	uv run ruff check app/ tests/
	uv run ruff format --check app/ tests/
	cd mock-exchange && uv run ruff check mock_exchange/
	cd ui && pnpm lint
	cd ops-ui && pnpm lint

format:
	uv run ruff check --fix app/ tests/
	uv run ruff format app/ tests/
	cd mock-exchange && uv run ruff check --fix mock_exchange/
	cd ui && pnpm lint:fix
	cd ops-ui && pnpm lint:fix

typecheck:
	uv run mypy app/
	cd ui && pnpm tsc --noEmit
	cd ops-ui && pnpm tsc --noEmit

tach-check:
	uv run tach check

test:
	uv run pytest

test-unit:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

check: lint typecheck tach-check test
