.PHONY: help install dev lint lint-all format format-check preflight test clean run worker beat flower embed-all monitoring-up monitoring-down system-and-monitoring system-and-monitoring-down docker-build docker-up docker-down docker-full docker-full-down docker-logs system system-down api-lint system-test

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
	@echo "  make monitoring-up           Start monitoring stack (Prometheus + Grafana + exporters)"
	@echo "  make monitoring-down         Stop monitoring stack"
	@echo "  make system-and-monitoring   Dev mode + monitoring stack"
	@echo "  make system-and-monitoring-down Stop dev mode + monitoring stack"
	@echo "  make docker-up               Start infra only (Qdrant + Redis)"
	@echo "  make docker-down             Stop infra"
	@echo "  make docker-full             Start ALL in Docker (infra + app + celery)"
	@echo "  make docker-full-down        Stop ALL Docker services"
	@echo "  make docker-logs             Tail Docker logs"
	@echo "  make docker-build            Build Docker images"
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
	@echo "📡 Installing Spectral (API linting)..."
	@command -v npm >/dev/null
	npm install -g @stoplight/spectral-cli
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
		spectral lint docs/openapi.yaml; \
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

monitoring-up:
	@echo "📈 Starting monitoring stack..."
	docker-compose --profile monitoring up -d

monitoring-down:
	@echo "🛑 Stopping monitoring stack..."
	docker-compose --profile monitoring stop
	docker-compose --profile monitoring rm -f

system-and-monitoring:
	@$(MAKE) system
	@$(MAKE) monitoring-up

system-and-monitoring-down:
	@$(MAKE) monitoring-down
	@$(MAKE) system-down

docker-build:
	@echo "🐳 Building Docker images..."
	docker-compose build

docker-up:
	@echo "🐳 Starting Qdrant + Redis..."
	docker-compose up -d
	@echo "✅ Services running:"
	@echo "   Qdrant: http://localhost:6333"
	@echo "   Redis:  localhost:6379"

docker-down:
	@echo "🛑 Stopping Docker infra (Qdrant + Redis)..."
	docker-compose down

docker-full:
	@echo "🐳 Starting FULL Docker stack (infra + app)..."
	docker-compose --profile full up -d --build
	@echo "✅ All services running in Docker:"
	@echo "   API:     http://localhost:8000"
	@echo "   Qdrant:  http://localhost:6333"
	@echo "   Redis:   localhost:6379"
	@echo "   Flower:  http://localhost:5555"

docker-full-down:
	@echo "🛑 Stopping full Docker stack..."
	docker-compose --profile full down

docker-logs:
	@echo "📜 Tailing Docker logs..."
	docker-compose logs -f --tail=200

system: docker-up
	@echo "🚀 Starting full ProfileBot stack in background..."
	@mkdir -p .logs
	@sh -c 'nohup uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000 > .logs/api.log 2>&1 & echo $$! > .logs/api.pid'
	@sh -c 'nohup uv run celery -A src.services.embedding.celery_app worker -l info -c 4 > .logs/worker.log 2>&1 & echo $$! > .logs/worker.pid'
	@sh -c 'nohup uv run celery -A src.services.embedding.celery_app beat -l info > .logs/beat.log 2>&1 & echo $$! > .logs/beat.pid'
	@sh -c 'nohup uv run celery -A src.services.embedding.celery_app flower --port=5555 > .logs/flower.log 2>&1 & echo $$! > .logs/flower.pid'
	@echo "✅ Started. Logs in .logs/*.log, PIDs in .logs/*.pid"

system-down: docker-down
	@echo "🛑 Stopping local ProfileBot processes..."
	@if [ -f .logs/api.pid ]; then kill $$(cat .logs/api.pid) || true; rm -f .logs/api.pid; fi
	@if [ -f .logs/worker.pid ]; then kill $$(cat .logs/worker.pid) || true; rm -f .logs/worker.pid; fi
	@if [ -f .logs/beat.pid ]; then kill $$(cat .logs/beat.pid) || true; rm -f .logs/beat.pid; fi
	@if [ -f .logs/flower.pid ]; then kill $$(cat .logs/flower.pid) || true; rm -f .logs/flower.pid; fi

# ============== Cleanup ==============

clean:
	@echo "🧹 Cleaning up..."
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
