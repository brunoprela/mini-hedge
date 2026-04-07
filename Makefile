.PHONY: up down logs restart install run-local run-ui run-ops-ui dev dev-stop migrate lint format gen-types typecheck tach-check test test-unit test-integration check db-reset kafka-reset redis-reset reset status mock-exchange-up mock-exchange-down mock-exchange-logs mock-exchange-status up-all down-all seed seed-trades seed-all backup restore load-test load-test-headless

# --- Platform Infrastructure ---

up:
	docker compose --profile core --profile frontend up -d --build

down:
	docker compose --profile core --profile frontend down

restart:
	docker compose --profile core --profile frontend restart

logs:
	docker compose --profile core --profile frontend logs -f

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

reset:
	@echo "Full reset — removing all volumes..."
	docker compose --profile core --profile frontend down -v
	@echo "Starting backend services..."
	docker compose --profile core up -d --build
	@echo "Waiting for Postgres..."
	@docker compose --profile core exec -T postgres sh -c 'until pg_isready -U minihedge; do sleep 1; done' 2>/dev/null
	@echo "Waiting for platform..."
	@until curl -sf http://localhost:8000/health > /dev/null 2>&1; do sleep 2; done
	@echo "Running migrations..."
	@$(MAKE) migrate
	@echo "Seeding data..."
	@$(MAKE) seed
	@echo "Ready. Run 'make dev' to start frontends."
	@echo "  Backend:   http://localhost:8000"
	@echo "  Keycloak:  http://localhost:8180"

# --- Development ---

install:
	uv sync
	pnpm install
	cd mock-exchange && uv sync

run-local:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-ui:
	cd ui && pnpm dev

run-ops-ui:
	cd ops-ui && pnpm dev

dev:
	@echo "Starting frontends locally (Turbopack)..."
	@cd ui && pnpm dev --turbopack &
	@cd ops-ui && pnpm dev --turbopack &
	@echo ""
	@echo "  UI:        http://localhost:3000"
	@echo "  Ops UI:    http://localhost:3100"
	@echo ""
	@echo "Press Ctrl+C to stop frontends."
	@wait

dev-stop:
	@echo "Stopping frontend dev servers..."
	-@pkill -f "next dev" 2>/dev/null || true

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

gen-types:
	@echo "Exporting OpenAPI schema from FastAPI..."
	uv run python packages/api-types/scripts/export_schema.py
	@echo "Generating TypeScript types..."
	cd packages/api-types && npx openapi-typescript generated/openapi.json -o generated/openapi.d.ts
	@echo "Types generated at packages/api-types/generated/"

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

lint-migrations:
	uv run python scripts/dump_migration_sql.py | npx squawk-cli --stdin-filepath=migrations.sql

check: lint typecheck tach-check test

# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------

backup:
	@bash scripts/backup.sh

restore:
	@bash scripts/restore.sh $(FILE)

# ---------------------------------------------------------------------------
# Load Testing (Locust)
# ---------------------------------------------------------------------------

load-test:
	@echo "Starting Locust load test..."
	@echo "  Web UI: http://localhost:8089"
	@echo "  Target: http://localhost:8000"
	@echo ""
	@echo "Set LOAD_TEST_PORTFOLIO_ID to a valid portfolio UUID before running."
	@echo "Example: LOAD_TEST_PORTFOLIO_ID=<uuid> make load-test"
	cd load_tests && pip install -q -r requirements.txt && \
		locust -f locustfile.py --host http://localhost:8000

load-test-headless:
	@echo "Running headless load test (50 users, 5/s spawn, 60s duration)..."
	cd load_tests && pip install -q -r requirements.txt && \
		locust -f locustfile.py --host http://localhost:8000 \
		--headless -u 50 -r 5 --run-time 60s \
		--csv=results/run
