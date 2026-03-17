.PHONY: help install dev lint lint-all format format-check preflight test clean run worker beat flower embed-all monitoring-up monitoring-down monitoring-create monitoring-build monitoring-rebuild monitoring-logs all-up all-down all-create all-build all-rebuild all-logs memory-probe-logs workflow-run qdrant-up qdrant-down qdrant-create qdrant-build qdrant-rebuild qdrant-logs redis-up redis-down redis-create redis-build redis-rebuild redis-logs api-up api-down api-create api-build api-rebuild api-logs celery-worker-up celery-worker-down celery-worker-create celery-worker-build celery-worker-rebuild celery-worker-logs celery-beat-up celery-beat-down celery-beat-create celery-beat-build celery-beat-rebuild celery-beat-logs flower-up flower-down flower-create flower-build flower-rebuild flower-logs prometheus-up prometheus-down prometheus-create prometheus-build prometheus-rebuild prometheus-logs grafana-up grafana-down grafana-create grafana-build grafana-rebuild grafana-logs redis-exporter-up redis-exporter-down redis-exporter-create redis-exporter-build redis-exporter-rebuild redis-exporter-logs celery-exporter-up celery-exporter-down celery-exporter-create celery-exporter-build celery-exporter-rebuild celery-exporter-logs queues-clean queues-clean-all system system-down api-lint system-test
COMPOSE ?= $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

ifneq (,$(wildcard .env))
  include .env
  export
endif

# Default target
help:
	@echo "ProfileBot - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install production dependencies"
	@echo "  make dev         Install dev dependencies + pre-commit hooks"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint        Run linters (ruff + mypy)"
	@echo "  make lint-all    Run linters (same as lint)"
	@echo "  make preflight   Run all local checks (lint + format check + api lint)"
	@echo "  make format      Format code with ruff"
	@echo "  make check       Run all checks (lint + format check)"
	@echo "  make api-lint    Lint OpenAPI spec with Spectral"
	@echo ""
	@echo "Testing:"
	@echo "  make test        Run tests with pytest"
	@echo "  make test-cov    Run tests with coverage"
	@echo "  make system-test Run system test scenario (e.g., SCENARIO=smoke)"
	@echo ""
	@echo "Run:"
	@echo "  make run                     Start the API server"
	@echo "  make worker                  Start Celery worker"
	@echo "  make beat                    Start Celery beat scheduler"
	@echo "  make flower                  Start Flower dashboard"
	@echo "  make embed-all               Trigger embedding from scraper"
	@echo "  make monitoring-build        Build monitoring images (no start)"
	@echo "  make monitoring-create       Create monitoring containers (no start)"
	@echo "  make monitoring-up           Start monitoring containers"
	@echo "  make monitoring-down         Stop + remove monitoring containers"
	@echo "  make monitoring-rebuild      Build + recreate monitoring containers"
	@echo "  make monitoring-logs         Tail monitoring logs (follow)"
	@echo "  make all-build               Build all images (ALL, no start)"
	@echo "  make all-create              Create all containers (ALL, no start)"
	@echo "  make all-up                  Start all containers (ALL)"
	@echo "  make all-down                Stop + remove all containers (ALL)"
	@echo "  make all-rebuild             Build + recreate all containers (ALL)"
	@echo "  make all-logs                Tail ALL logs (follow)"
	@echo "  make memory-probe-logs       Tail Celery memory probe logs"
	@echo "  make workflow-run            Trigger main ingestion workflow"
	@echo "  make queues-clean            Revoke active Celery tasks, purge queues, flush Redis"
	@echo "  make queues-clean-all        Deep cleanup (revoke, purge, FLUSHALL)"
	@echo "  make <service>-up            Start a single service container"
	@echo "  make <service>-down          Stop + remove a single service container"
	@echo "  make <service>-create        Create a single service container (no start)"
	@echo "  make <service>-build         Build a single service image (no start)"
	@echo "  make <service>-rebuild       Build + recreate a single service"
	@echo "  make <service>-logs          Tail logs for a single service (follow)"
	@echo "  services: qdrant redis api celery-worker celery-beat flower prometheus grafana redis-exporter celery-exporter"
	@echo "  make system                  Dev mode: infra in Docker + app local (uv run)"
	@echo "  make system-down             Stop dev mode (infra + local processes)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       Remove cache and build files"

# ============== Setup ==============

install:
	@echo "📦 Installing dependencies with uv..."
	uv venv --clear
	uv pip install -r pyproject.toml

dev: install
	@echo "🔧 Installing dev dependencies..."
	uv pip install -e ".[dev]"
	@echo "🪝 Setting up pre-commit hooks..."
	uv run pre-commit install --install-hooks
	@echo "📡 Spectral setup..."
	@if command -v spectral >/dev/null 2>&1; then \
		echo "✅ Spectral CLI found in PATH."; \
	elif command -v docker >/dev/null 2>&1; then \
		echo "ℹ️ Spectral will run via Docker in api-lint."; \
	else \
		echo "⚠️ Spectral not found. Install @stoplight/spectral-cli or Docker."; \
	fi
	@echo "✅ Dev environment ready!"

# ============== Code Quality ==============

lint: dev
	@echo "🔍 Running linters..."
	uv run ruff check src/ tests/
	uv run mypy src/ --ignore-missing-imports

lint-all: lint
	@echo "🔍 Linting complete."

pylint: lint
	@echo "✅ Ruff + mypy completed."

format:
	@echo "✨ Formatting code..."
	uv run ruff format src/ tests/
	uv run ruff check src/ tests/ --fix

format-check:
	@echo "🔍 Checking format..."
	uv run ruff format --check src/ tests/

preflight: lint-all format-check api-lint
	@echo "✅ Preflight checks passed!"

check: lint format-check
	@echo "✅ All checks passed!"

api-lint:
	@echo "📡 Linting OpenAPI spec with Spectral..."
	@if [ -f "docs/openapi.yaml" ]; then \
		if command -v spectral >/dev/null 2>&1; then \
			spectral lint docs/openapi.yaml; \
		elif command -v docker >/dev/null 2>&1; then \
			docker run --rm -v "$(PWD)":/work -w /work stoplight/spectral:latest lint docs/openapi.yaml; \
		else \
			echo "❌ Spectral not found. Install @stoplight/spectral-cli or Docker."; \
			exit 1; \
		fi; \
	else \
		echo "❌ Missing OpenAPI spec at docs/openapi.yaml"; \
		exit 1; \
	fi

# ============== Testing ==============

test:
	@echo "🧪 Running tests..."
	uv run pytest tests/ -v

test-cov:
	@echo "🧪 Running tests with coverage..."
	uv run pytest tests/ -v --cov=src --cov-report=html --cov-report=term
	@echo "📊 Coverage report: htmlcov/index.html"

system-test:
	@if [ -z "$(SCENARIO)" ]; then \
		echo "❌ Missing SCENARIO. Usage: make system-test SCENARIO=smoke"; \
		exit 1; \
	fi
	@echo "🧪 Running system test scenario: $(SCENARIO)"
	uv run pytest tests/system/test_$(SCENARIO)_system.py -v

# ============== Run ==============

run:
	@echo "🚀 Starting ProfileBot API..."
	uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	@echo "🧵 Starting Celery worker..."
	uv run celery -A src.services.embedding.celery_app worker -l info -c 4

beat:
	@echo "⏲️ Starting Celery beat..."
	uv run celery -A src.services.embedding.celery_app beat -l info

flower:
	@echo "🌸 Starting Flower dashboard..."
	uv run celery -A src.services.embedding.celery_app flower --port=5555

embed-all:
	@echo "🧩 Triggering embedding from scraper..."
	@uv run python -c 'from src.services.embedding.tasks import embed_from_scraper_task; print(embed_from_scraper_task.run())'

monitoring-build:
	@echo "🐳 Building monitoring images..."
	$(COMPOSE) --profile monitoring build

monitoring-create:
	@echo "🐳 Creating monitoring containers..."
	$(COMPOSE) --profile monitoring create

monitoring-up:
	@echo "📈 Starting monitoring stack..."
	$(COMPOSE) --profile monitoring up -d

monitoring-down:
	@echo "🛑 Stopping monitoring stack..."
	$(COMPOSE) --profile monitoring down

monitoring-logs:
	@echo "📄 Tailing monitoring logs..."
	$(COMPOSE) --profile monitoring logs -f --tail=200

monitoring-rebuild:
	@echo "♻️ Rebuilding monitoring stack..."
	$(COMPOSE) --profile monitoring up -d --build --force-recreate

all-build:
	@echo "🐳 Building ALL images..."
	$(COMPOSE) --profile full --profile monitoring build

all-create:
	@echo "🐳 Creating ALL containers..."
	$(COMPOSE) --profile full --profile monitoring create

all-up:
	@echo "🐳 Starting ALL containers..."
	$(COMPOSE) --profile full --profile monitoring up -d

all-down:
	@echo "🛑 Stopping ALL containers..."
	$(COMPOSE) --profile full --profile monitoring down

all-logs:
	@echo "📄 Tailing ALL logs..."
	$(COMPOSE) --profile full --profile monitoring logs -f --tail=200

memory-probe-logs:
	@echo "📄 Tailing memory probe logs..."
	$(COMPOSE) --profile full logs -f --tail=200 api celery-worker | grep --line-buffered "memory_probe"

workflow-run:
	@echo "🚀 Triggering main ingestion workflow..."
	$(COMPOSE) --profile full exec -T celery-worker python -c "from src.services.embedding.celery_app import celery_app; result = celery_app.send_task('workflow.run_ingestion'); print('Workflow triggered:', result.id)"

all-rebuild:
	@echo "♻️ Rebuilding ALL containers..."
	$(COMPOSE) --profile full --profile monitoring up -d --build --force-recreate

qdrant-build:
	$(COMPOSE) build qdrant

qdrant-create:
	$(COMPOSE) create qdrant

qdrant-up:
	$(COMPOSE) up -d qdrant

qdrant-down:
	$(COMPOSE) stop qdrant
	$(COMPOSE) rm -f qdrant

qdrant-rebuild:
	$(COMPOSE) up -d --build --force-recreate qdrant

qdrant-logs:
	$(COMPOSE) logs -f --tail=200 qdrant

redis-build:
	$(COMPOSE) build redis

redis-create:
	$(COMPOSE) create redis

redis-up:
	$(COMPOSE) up -d redis

redis-down:
	$(COMPOSE) stop redis
	$(COMPOSE) rm -f redis

redis-rebuild:
	$(COMPOSE) up -d --build --force-recreate redis

redis-logs:
	$(COMPOSE) logs -f --tail=200 redis

api-build:
	$(COMPOSE) --profile full build --no-cache api

api-create:
	$(COMPOSE) --profile full create api

api-up:
	$(COMPOSE) --profile full up -d api

api-down:
	$(COMPOSE) --profile full stop api
	$(COMPOSE) --profile full rm -f api

api-rebuild:
	$(COMPOSE) --profile full build --no-cache api
	$(COMPOSE) --profile full up -d --force-recreate api

api-logs:
	$(COMPOSE) --profile full logs -f --tail=200 api

celery-worker-build:
	$(COMPOSE) --profile full build celery-worker

celery-worker-create:
	$(COMPOSE) --profile full create celery-worker

celery-worker-up:
	$(COMPOSE) --profile full up -d celery-worker

celery-worker-down:
	$(COMPOSE) --profile full stop celery-worker
	$(COMPOSE) --profile full rm -f celery-worker

celery-worker-rebuild:
	$(COMPOSE) --profile full up -d --build --force-recreate celery-worker

celery-worker-logs:
	$(COMPOSE) --profile full logs -f --tail=200 celery-worker

celery-beat-build:
	$(COMPOSE) --profile full build celery-beat

celery-beat-create:
	$(COMPOSE) --profile full create celery-beat

celery-beat-up:
	$(COMPOSE) --profile full up -d celery-beat

celery-beat-down:
	$(COMPOSE) --profile full stop celery-beat
	$(COMPOSE) --profile full rm -f celery-beat

celery-beat-rebuild:
	$(COMPOSE) --profile full up -d --build --force-recreate celery-beat

celery-beat-logs:
	$(COMPOSE) --profile full logs -f --tail=200 celery-beat

flower-build:
	$(COMPOSE) --profile full build flower

flower-create:
	$(COMPOSE) --profile full create flower

flower-up:
	$(COMPOSE) --profile full up -d flower

flower-down:
	$(COMPOSE) --profile full stop flower
	$(COMPOSE) --profile full rm -f flower

flower-rebuild:
	$(COMPOSE) --profile full up -d --build --force-recreate flower

flower-logs:
	$(COMPOSE) --profile full logs -f --tail=200 flower

prometheus-build:
	$(COMPOSE) --profile monitoring build prometheus

prometheus-create:
	$(COMPOSE) --profile monitoring create prometheus

prometheus-up:
	$(COMPOSE) --profile monitoring up -d prometheus

prometheus-down:
	$(COMPOSE) --profile monitoring stop prometheus
	$(COMPOSE) --profile monitoring rm -f prometheus

prometheus-rebuild:
	$(COMPOSE) --profile monitoring up -d --build --force-recreate prometheus

prometheus-logs:
	$(COMPOSE) --profile monitoring logs -f --tail=200 prometheus

grafana-build:
	$(COMPOSE) --profile monitoring build grafana

grafana-create:
	$(COMPOSE) --profile monitoring create grafana

grafana-up:
	$(COMPOSE) --profile monitoring up -d grafana

grafana-down:
	$(COMPOSE) --profile monitoring stop grafana
	$(COMPOSE) --profile monitoring rm -f grafana

grafana-rebuild:
	$(COMPOSE) --profile monitoring up -d --build --force-recreate grafana

grafana-logs:
	$(COMPOSE) --profile monitoring logs -f --tail=200 grafana

redis-exporter-build:
	$(COMPOSE) --profile monitoring build redis-exporter

redis-exporter-create:
	$(COMPOSE) --profile monitoring create redis-exporter

redis-exporter-up:
	$(COMPOSE) --profile monitoring up -d redis-exporter

redis-exporter-down:
	$(COMPOSE) --profile monitoring stop redis-exporter
	$(COMPOSE) --profile monitoring rm -f redis-exporter

redis-exporter-rebuild:
	$(COMPOSE) --profile monitoring up -d --build --force-recreate redis-exporter

redis-exporter-logs:
	$(COMPOSE) --profile monitoring logs -f --tail=200 redis-exporter

celery-exporter-build:
	$(COMPOSE) --profile monitoring build celery-exporter

celery-exporter-create:
	$(COMPOSE) --profile monitoring create celery-exporter

celery-exporter-up:
	$(COMPOSE) --profile monitoring up -d celery-exporter

celery-exporter-down:
	$(COMPOSE) --profile monitoring stop celery-exporter
	$(COMPOSE) --profile monitoring rm -f celery-exporter

celery-exporter-rebuild:
	$(COMPOSE) --profile monitoring up -d --build --force-recreate celery-exporter

celery-exporter-logs:
	$(COMPOSE) --profile monitoring logs -f --tail=200 celery-exporter

queues-clean:
	@echo "🧹 Cleaning Redis + Celery queues..."
	@ACTIVE_IDS=$$(docker exec profilebot-celery-worker celery -A src.services.embedding.celery_app inspect active --json | python -c 'import json,sys; data=json.load(sys.stdin); ids=[]; [ids.extend([t.get("id") for t in tasks if t.get("id")]) for tasks in data.values() if isinstance(tasks, list)]; print(" ".join(ids))'); \
	if [ -n "$$ACTIVE_IDS" ]; then \
		docker exec profilebot-celery-worker celery -A src.services.embedding.celery_app control revoke $$ACTIVE_IDS; \
		docker exec profilebot-celery-worker celery -A src.services.embedding.celery_app control terminate SIGTERM $$ACTIVE_IDS; \
	else \
		echo "No active tasks to revoke"; \
	fi
	@docker exec profilebot-celery-worker celery -A src.services.embedding.celery_app purge -f
	@docker exec profilebot-redis redis-cli FLUSHALL
	@echo "✅ Done"

queues-clean-all: queues-clean

system: qdrant-up redis-up
	@echo "🚀 Starting full ProfileBot stack in background..."
	@mkdir -p .logs
	@sh -c 'nohup uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000 > .logs/api.log 2>&1 & echo $$! > .logs/api.pid'
	@sh -c 'nohup uv run celery -A src.services.embedding.celery_app worker -l info -c 4 > .logs/worker.log 2>&1 & echo $$! > .logs/worker.pid'
	@sh -c 'nohup uv run celery -A src.services.embedding.celery_app beat -l info > .logs/beat.log 2>&1 & echo $$! > .logs/beat.pid'
	@sh -c 'nohup uv run celery -A src.services.embedding.celery_app flower --port=5555 > .logs/flower.log 2>&1 & echo $$! > .logs/flower.pid'
	@echo "✅ Started. Logs in .logs/*.log, PIDs in .logs/*.pid"

system-down: qdrant-down redis-down
	@echo "🛑 Stopping local ProfileBot processes..."
	@if [ -f .logs/api.pid ]; then kill $$(cat .logs/api.pid) || true; rm -f .logs/api.pid; fi
	@if [ -f .logs/worker.pid ]; then kill $$(cat .logs/worker.pid) || true; rm -f .logs/worker.pid; fi
	@if [ -f .logs/beat.pid ]; then kill $$(cat .logs/beat.pid) || true; rm -f .logs/beat.pid; fi
	@if [ -f .logs/flower.pid ]; then kill $$(cat .logs/flower.pid) || true; rm -f .logs/flower.pid; fi

# ============== Cleanup ==============

clean:
	@echo "🧹 Cleaning up..."
	@echo "🧹 Removing Qdrant data volume..."
	@$(COMPOSE) stop qdrant
	@$(COMPOSE) rm -f qdrant
	@docker volume rm -f profilebot_qdrant_storage qdrant_storage 2>/dev/null || true
	rm -rf .venv/
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf *.egg-info/
	rm -rf dist/
	rm -rf build/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Clean!"
