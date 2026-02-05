# ProfileBot

Sistema AI per il matching di profili professionali basato su competenze (skill-first approach).

## Descrizione

ProfileBot è un'applicazione aziendale che permette la ricerca e analisi dei profili interni, combinando:
- **Curriculum** (docx) con esperienze e skill in formato keyword
- **Stato operativo** (disponibilità/allocazione) da fonti esterne

### Funzionalità MVP

1. **Ricerca profili per skill** - Trovare profili in base a competenze specifiche
2. **Analisi disponibilità** - Identificare profili disponibili, parzialmente allocati o liberi
3. **Match con job description** - Trovare il miglior profilo per una posizione specifica

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python 3.11+ |
| Package Manager | [uv](https://github.com/astral-sh/uv) |
| RAG Framework | LlamaIndex |
| Vector Store | Qdrant |
| LLM | OpenAI / Azure OpenAI |
| Queue | Redis |
| API | FastAPI |

## Quick Start

```bash
# Clone repository
git clone https://github.com/giamma80/profilebot.git
cd profilebot

# Setup dev environment (richiede uv installato)
make dev

# Oppure manualmente:
uv venv
uv pip install -e ".[dev]"
uv run pre-commit install

# Configure
cp .env.example .env
# Edit .env with your settings

# Start services
make docker-up    # Qdrant + Redis

# Run API
make run
```

## Makefile Commands

```bash
# Setup
make install      # Install production dependencies
make dev          # Install dev dependencies + pre-commit hooks

# Code Quality
make lint         # Run fast linters (ruff + flake8 + mypy)
make lint-all     # Run ALL linters (+ pylint)
make pylint       # Run only pylint
make format       # Format code (black + isort + ruff --fix)
make check        # Run all checks (lint + format check)
make api-lint     # Lint OpenAPI spec with Spectral

# Testing
make test         # Run tests with pytest
make test-cov     # Run tests with coverage report

# Run
make run          # Start API server (uvicorn)
make docker-up    # Start Qdrant + Redis
make docker-down  # Stop Docker services

# Cleanup
make clean        # Remove cache and build files
```

## Code Quality Stack

| Tool | Purpose | Command |
|------|---------|---------|
| **ruff** | Fast linter (Rust-based) | `make lint` |
| **flake8** | PEP8 compliance | `make lint` |
| **pylint** | Deep static analysis | `make pylint` |
| **mypy** | Type checking | `make lint` |
| **black** | Code formatter | `make format` |
| **isort** | Import sorting | `make format` |
| **bandit** | Security scanning | CI only |
| **spectral** | OpenAPI linting | `make api-lint` |

## CI/CD

GitHub Actions pipeline runs on every push/PR:

- **Lint & Format** - ruff, flake8, black, isort, mypy, pylint
- **Tests** - pytest with coverage
- **Security** - bandit security scan

## Architettura

```
Client (Chatbot)
       │
       ▼
Backend RAG API ──► Filtro Disponibilità
       │                    │
       ▼                    ▼
Filtro Metadata (skill_domain, seniority)
       │
       ▼
Qdrant – cv_skills (vector search)
       │
       ▼
Shortlist cv_id
       │
       ▼
Qdrant – cv_experiences (supporto)
       │
       ▼
LLM ──► Decisione spiegata
```

## Project Structure

```
profilebot/
├── src/
│   ├── api/          # FastAPI endpoints
│   ├── core/         # Core business logic
│   ├── services/     # External services (Qdrant, LLM)
│   └── utils/        # Utilities
├── tests/            # Test suite
├── docs/             # Documentation
├── scripts/          # Utility scripts
├── .github/
│   ├── workflows/    # CI/CD pipelines
│   └── ISSUE_TEMPLATE/
├── Makefile          # Project automation
├── pyproject.toml    # Dependencies & tool config
├── docker-compose.yml
└── .pre-commit-config.yaml
```

## Development

### Pre-commit Hooks

Pre-commit hooks are installed automatically with `make dev`. They run:
- trailing-whitespace, end-of-file-fixer
- ruff (with auto-fix)
- black
- mypy

### Adding Dependencies

```bash
# Add production dependency
uv add <package>

# Add dev dependency
uv add --dev <package>
```

## Team

| Ruolo | Responsabilità |
|-------|----------------|
| Product Owner | Priorità backlog, requisiti business |
| Solution Architect | Architettura, decisioni tecniche |
| Data Scientist | Pipeline ML, embedding, ottimizzazione |
| Backend Developer | API, integrations, core logic |
| Frontend Developer | UI/UX chatbot interface |

## Documentation

- [Analisi Preliminare](docs/analisi_preliminare.md)
- [Appendice Tecnica - Indexing](docs/Appendice%20tecnica%20—%20Indexing.md)
- [Team Structure](docs/TEAM_STRUCTURE.md)
- [Product Backlog](docs/BACKLOG.md)

## License

Proprietario - Uso interno aziendale
