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

---

## Architettura

### System Architecture

```mermaid
flowchart TB
    subgraph Client["🖥️ Client Layer"]
        UI[Chatbot Interface]
    end

    subgraph API["⚡ API Layer"]
        FastAPI[FastAPI Backend]
        SearchAPI["/api/v1/search/skills"]
        MatchAPI["/api/v1/match/job"]
    end

    subgraph Core["🧠 Core Processing"]
        Parser[CV Parser<br/>python-docx]
        SkillExtractor[Skill Extractor<br/>+ Normalizer]
        Embedder[Embedding Service<br/>OpenAI/Sentence-Transformers]
    end

    subgraph Storage["💾 Data Storage"]
        Qdrant[(Qdrant<br/>Vector Store)]
        Redis[(Redis<br/>Cache)]
        SkillDict[("📚 Skill Dictionary<br/>YAML")]
    end

    subgraph External["🔗 External Sources"]
        SharePoint[SharePoint<br/>Availability Status]
        CVSource[CV Source<br/>DOCX Files]
    end

    subgraph LLM["🤖 LLM Layer"]
        OpenAI[OpenAI / Azure OpenAI<br/>GPT-4]
    end

    UI --> FastAPI
    FastAPI --> SearchAPI
    FastAPI --> MatchAPI

    SearchAPI --> Embedder
    SearchAPI --> Qdrant
    SearchAPI --> Redis

    MatchAPI --> OpenAI
    MatchAPI --> Qdrant
    MatchAPI --> Redis

    CVSource --> Parser
    Parser --> SkillExtractor
    SkillExtractor --> SkillDict
    SkillExtractor --> Embedder
    Embedder --> Qdrant

    SharePoint --> Redis

    Qdrant --> OpenAI
```

### Data Flow - Search by Skills

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant E as Embedder
    participant Q as Qdrant
    participant R as Redis
    participant LLM as OpenAI

    U->>API: POST /search/skills<br/>{skills: ["python", "fastapi"]}
    API->>E: Generate query embedding
    E-->>API: embedding vector

    API->>R: Check availability cache
    R-->>API: available cv_ids

    API->>Q: Vector search<br/>+ metadata filters
    Q-->>API: Top K matches

    API->>API: Calculate scores<br/>& matched skills
    API-->>U: ProfileMatch[]
```

### Data Flow - Job Description Match

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant LLM as OpenAI
    participant Q as Qdrant
    participant R as Redis

    U->>API: POST /match/job<br/>{job_description: "..."}

    API->>LLM: Extract skills from JD
    LLM-->>API: {must_have, nice_to_have}

    API->>Q: Vector search shortlist
    Q-->>API: Top 20 candidates

    API->>R: Filter by availability
    R-->>API: Filtered candidates

    API->>Q: Fetch experiences<br/>for shortlist
    Q-->>API: Experience context

    API->>LLM: Rank & explain
    LLM-->>API: Ranked candidates<br/>with explanations

    API-->>U: CandidateMatch[]
```

### Qdrant Collections

```mermaid
erDiagram
    CV_SKILLS {
        string cv_id PK
        vector embedding
        string[] normalized_skills
        string skill_domain
        string seniority_bucket
        string dictionary_version
        datetime indexed_at
    }

    CV_EXPERIENCES {
        string cv_id FK
        string experience_id PK
        vector embedding
        string[] related_skills
        int experience_years
        datetime indexed_at
    }

    AVAILABILITY_CACHE {
        string cv_id PK
        string status
        int allocation_pct
        string current_project
        datetime updated_at
    }

    CV_SKILLS ||--o{ CV_EXPERIENCES : "cv_id"
    CV_SKILLS ||--|| AVAILABILITY_CACHE : "cv_id"
```

---

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python 3.11+ |
| Package Manager | [uv](https://github.com/astral-sh/uv) |
| RAG Framework | LlamaIndex |
| Vector Store | Qdrant |
| LLM | OpenAI / Azure OpenAI |
| Cache | Redis |
| API | FastAPI |

---

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

### Docker build exclusions

Le build Docker escludono file e directory locali/temporanei tramite `.dockerignore`.
Esempi esclusi: `.venv`, `__pycache__`, `.env*`, `qdrant_storage/`, `redis_data/`, `logs/`, `.git/`.
Questo evita di includere segreti o artefatti di sviluppo nelle immagini.

---

## Development Workflow

### Git Flow

Ogni User Story deve avere un **feature branch dedicato**:

```
feature/US-XXX-descrizione-breve
```

**Workflow:**
1. Crea branch da `main`
2. Sviluppa con commit atomici (Conventional Commits)
3. Push e apri Pull Request
4. Code review + CI green
5. Squash merge su main

```mermaid
gitGraph
    commit id: "main"
    branch feature/US-002-qdrant
    checkout feature/US-002-qdrant
    commit id: "feat: add Qdrant client"
    commit id: "test: add connection tests"
    checkout main
    merge feature/US-002-qdrant tag: "PR #12"
```

### Branch Types

| Prefix | Uso |
|--------|-----|
| `feature/` | User Stories |
| `bugfix/` | Bug fixes |
| `hotfix/` | Fix urgenti |
| `docs/` | Documentazione |

### Commit Convention

```bash
feat(parser): add DOCX text extraction
fix(qdrant): handle connection timeout
test(skills): add normalization tests
docs: update API documentation
```

📖 **Vedi [CONTRIBUTING.md](docs/CONTRIBUTING.md) per dettagli completi**

---

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

---

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

---

## CI/CD

GitHub Actions pipeline runs on every push/PR:

- **Lint & Format** - ruff, flake8, black, isort, mypy, pylint
- **Tests** - pytest with coverage
- **Security** - bandit security scan

---

## Project Structure

```
profilebot/
├── src/
│   ├── api/              # FastAPI endpoints
│   │   └── v1/           # API version 1
│   ├── core/             # Core business logic
│   │   ├── parser/       # CV parsing
│   │   ├── skills/       # Skill extraction
│   │   └── indexing/     # Embedding pipeline
│   ├── services/         # External services
│   │   ├── qdrant/       # Vector store
│   │   ├── embedding/    # Embedding generation
│   │   └── availability/ # Status service
│   └── utils/            # Utilities
├── data/
│   └── skills_dictionary.yaml
├── tests/                # Test suite
├── docs/                 # Documentation
├── scripts/              # Utility scripts
├── .github/
│   ├── workflows/        # CI/CD pipelines
│   └── ISSUE_TEMPLATE/
├── Makefile              # Project automation
├── pyproject.toml        # Dependencies & tool config
├── docker-compose.yml
└── .pre-commit-config.yaml
```

---

## User Stories MVP

| ID | Titolo | Sprint | Priority |
|----|--------|--------|----------|
| US-001 | Setup Repository e CI/CD | 1 | P0 |
| US-002 | Setup Qdrant Vector Store | 1 | P0 |
| US-003 | Parser CV DOCX | 1 | P0 |
| US-004 | Skill Extraction e Normalizzazione | 2 | P0 |
| US-005 | Embedding e Indexing Pipeline | 2 | P0 |
| US-006 | API Ricerca Profili per Skill | 3 | P1 |
| US-007 | Filtro Disponibilità | 3 | P1 |
| US-008 | Match con Job Description | 4 | P1 |

📖 **Vedi [USER_STORIES_DETAILED.md](docs/USER_STORIES_DETAILED.md) per specifiche complete**

---

## Team

| Ruolo | Responsabilità |
|-------|----------------|
| Product Owner | Priorità backlog, requisiti business |
| Solution Architect | Architettura, decisioni tecniche |
| Data Scientist | Pipeline ML, embedding, ottimizzazione |
| Backend Developer | API, integrations, core logic |
| Frontend Developer | UI/UX chatbot interface |

---

## Documentation

- [User Stories Dettagliate](docs/USER_STORIES_DETAILED.md)
- [Contributing Guide](docs/CONTRIBUTING.md)
- [Analisi Preliminare](docs/analisi_preliminare.md)
- [Appendice Tecnica - Indexing](docs/Appendice%20tecnica%20—%20Indexing.md)
- [Team Structure](docs/TEAM_STRUCTURE.md)
- [Product Backlog](docs/BACKLOG.md)

---

## License

Proprietario - Uso interno aziendale
