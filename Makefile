.PHONY: help install dev lint format test clean run docker-up docker-down

# Default target
help:
	@echo "ProfileBot - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install production dependencies"
	@echo "  make dev         Install dev dependencies + pre-commit hooks"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint        Run linters (ruff + flake8 + mypy)"
	@echo "  make format      Format code with black + isort"
	@echo "  make check       Run all checks (lint + format check)"
	@echo ""
	@echo "Testing:"
	@echo "  make test        Run tests with pytest"
	@echo "  make test-cov    Run tests with coverage"
	@echo ""
	@echo "Run:"
	@echo "  make run         Start the API server"
	@echo "  make docker-up   Start Qdrant + Redis"
	@echo "  make docker-down Stop Docker services"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       Remove cache and build files"

# ============== Setup ==============

install:
	@echo "📦 Installing dependencies with uv..."
	uv venv
	uv pip install -r pyproject.toml

dev: install
	@echo "🔧 Installing dev dependencies..."
	uv pip install -e ".[dev]"
	@echo "🪝 Setting up pre-commit hooks..."
	uv run pre-commit install
	@echo "✅ Dev environment ready!"

# ============== Code Quality ==============

lint:
	@echo "🔍 Running linters..."
	uv run ruff check src/ tests/
	uv run flake8 src/ tests/ --max-line-length=100 --ignore=E501,W503
	uv run mypy src/ --ignore-missing-imports

format:
	@echo "✨ Formatting code..."
	uv run isort src/ tests/
	uv run black src/ tests/

format-check:
	@echo "🔍 Checking format..."
	uv run isort --check-only src/ tests/
	uv run black --check src/ tests/

check: lint format-check
	@echo "✅ All checks passed!"

# ============== Testing ==============

test:
	@echo "🧪 Running tests..."
	uv run pytest tests/ -v

test-cov:
	@echo "🧪 Running tests with coverage..."
	uv run pytest tests/ -v --cov=src --cov-report=html --cov-report=term
	@echo "📊 Coverage report: htmlcov/index.html"

# ============== Run ==============

run:
	@echo "🚀 Starting ProfileBot API..."
	uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

docker-up:
	@echo "🐳 Starting Qdrant + Redis..."
	docker-compose up -d
	@echo "✅ Services running:"
	@echo "   Qdrant: http://localhost:6333"
	@echo "   Redis:  localhost:6379"

docker-down:
	@echo "🛑 Stopping Docker services..."
	docker-compose down

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
