# Copilot Code Review Instructions - ProfileBot

## Github URL
### Github projectissue tracking per US: `US-XXX` (e.g. `US-001`, `US-002`, `US-003`)
project: https://github.com/users/giamma80/projects/2
### Versioning e code review tramite PR su branch `feature/US-XXX-descrizione-breve`
repo: https://github.com/giamma80/ProfileBot


> **Scope:** Queste linee guida si applicano a tutto il codice ProfileBot: backend Python, servizi, API, test e documentazione.

---

## Project Overview

**ProfileBot** è un sistema AI per il matching di profili professionali basato su competenze (skill-first approach).

### Componenti Principali
- **Backend API**: FastAPI con Python 3.11+
- **Vector Store**: Qdrant per ricerca semantica
- **RAG Strategy**: Custom (Qdrant + OpenAI + retrieval + prompt)
- **Cache**: Redis per stato disponibilità
- **LLM**: OpenAI / Azure OpenAI

#### RAG Strategy (Technical)
- **Retrieval**: embedding query → Qdrant vector search (`cv_skills`), con filtri su `res_id`, `skill_domain`, `seniority` e paginazione.
- **Context building**: aggregazione `matched_skills`, `missing_skills`, metadata e score (cosine + match ratio).
- **Prompting**: contesto strutturato passato a OpenAI per ranking/spiegazioni quando richiesto.
- **Why not LlamaIndex**: flusso semplice e controllato, meno dipendenze, tuning di ranking/filtri e performance più diretto; framework dedicati sono superflui finché non servono pipeline complesse (routing, caching avanzato, multi-index orchestration).

### Architettura
```
src/
├── api/           # FastAPI endpoints
│   └── v1/        # Versioned API
├── core/          # Business logic
│   ├── parser/    # CV parsing
│   ├── skills/    # Skill extraction
│   ├── indexing/  # Embedding pipeline
│   └── llm/       # LLM integration
├── services/      # External services
│   ├── qdrant/    # Vector store
│   ├── embedding/ # Embedding generation
│   └── availability/ # Status service
└── utils/         # Utilities
```

---

## 1. Git Workflow & Branch Management

### Branch Naming Convention
```
feature/US-XXX-descrizione-breve
bugfix/XXX-descrizione
hotfix/critical-fix
docs/update-readme
refactor/cleanup-module
```

**Esempi:**
```
feature/US-003-cv-parser
bugfix/123-fix-embedding-timeout
docs/update-api-documentation
```

### Commit Message Standards

Usiamo [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
| Type | Uso |
|------|-----|
| `feat` | Nuova funzionalità |
| `fix` | Bug fix |
| `docs` | Documentazione |
| `style` | Formattazione (no logic change) |
| `refactor` | Refactoring |
| `test` | Test |
| `chore` | Build, CI, dependencies |

**Scopes:**
| Scope | Area |
|-------|------|
| `parser` | CV parsing |
| `skills` | Skill extraction |
| `qdrant` | Vector store |
| `api` | FastAPI endpoints |
| `llm` | LLM integration |
| `ci` | CI/CD pipeline |

**Esempi:**
```bash
feat(parser): add DOCX metadata extraction
fix(qdrant): handle connection timeout gracefully
test(skills): add normalization edge cases
docs(api): update OpenAPI schema
chore(ci): add ruff to GitHub Actions
```

### Pull Request Guidelines

**Title Format:** `[US-XXX] Titolo descrittivo`

**Required Sections:**
- **Description**: Cosa fa la PR, perché, decisioni di design
- **Related Issue**: `Closes #XX`
- **Type of Change**: Feature, Bug fix, Refactoring, Documentation
- **Checklist**: Tests, Docs, Linting
- **Testing**: Come testare le modifiche

---

## 2. Python Code Standards

### Technology Stack
- **Language**: Python 3.11+
- **Package Manager**: `uv`
- **Framework**: FastAPI
- **Validation**: Pydantic v2
- **Testing**: pytest
- **Linting**: ruff, mypy, bandit
- **Formatting**: ruff

### Code Style

#### Preflight Formalisms (make preflight)
- **Ruff check**: rispettare tutte le regole abilitate in `pyproject.toml` (nessuna eccezione locale non motivata).
- **Import ordering**: organizzare import in 3 blocchi (standard library, third-party, local) con una riga vuota tra i blocchi.
- **`__all__`**: se presente, deve essere **ordinato in stile isort** (alfabetico, case-sensitive) e definito come lista/tupla letterale.
- **Format**: il formato deve essere conforme a `ruff format --check` (niente formattazioni manuali divergenti).
- **Type hints**: obbligatori sulle funzioni pubbliche (mypy).
- **Logging**: usare lazy formatting con `%s`, mai f-string nei log (ruff).
- **Error handling**: usare eccezioni specifiche, no `except: pass` (ruff).
- **API lint**: `docs/openapi.yaml` deve esistere e passare `spectral lint`.

#### Import Organization
```python
# Standard library
from __future__ import annotations
import os
from datetime import datetime
from typing import Optional

# Third-party
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local
from src.core.parser import parse_cv
from src.services.qdrant import get_qdrant_client
```

#### Type Hints (OBBLIGATORI)
```python
# ✅ Corretto
def process_cv(file_path: str, options: ParseOptions | None = None) -> ParsedCV:
    ...

# ❌ Evitare
def process_cv(file_path, options=None):
    ...
```

#### Pydantic Models
```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CVMetadata(BaseModel):
    """Metadata estratti dal CV."""

    cv_id: str = Field(..., description="Identificativo univoco")
    file_name: str
    full_name: Optional[str] = None
    current_role: Optional[str] = None
    parsed_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"frozen": True}  # Immutabile
```

#### Docstrings (Google Style)
```python
def extract_skills(text: str, dictionary: SkillDictionary) -> list[NormalizedSkill]:
    """Estrae e normalizza le skill da un testo.

    Args:
        text: Testo raw contenente le skill.
        dictionary: Dizionario per la normalizzazione.

    Returns:
        Lista di skill normalizzate con confidence score.

    Raises:
        SkillExtractionError: Se il testo è vuoto o malformato.

    Example:
        >>> skills = extract_skills("Python, FastAPI", dict)
        >>> skills[0].canonical
        'python'
    """
```

### Error Handling

#### Custom Exceptions
```python
# src/core/exceptions.py
class ProfileBotError(Exception):
    """Base exception per ProfileBot."""
    pass

class CVParseError(ProfileBotError):
    """Errore durante il parsing del CV."""
    def __init__(self, file_path: str, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Failed to parse '{file_path}': {reason}")

class SkillExtractionError(ProfileBotError):
    """Errore durante l'estrazione delle skill."""
    pass
```

#### Exception Handling Pattern
```python
import logging

logger = logging.getLogger(__name__)

def process_cv(file_path: str) -> ParsedCV:
    try:
        return _do_parse(file_path)
    except FileNotFoundError:
        logger.error("CV file not found: '%s'", file_path)
        raise CVParseError(file_path, "File not found")
    except Exception as e:
        logger.exception("Unexpected error parsing CV: '%s'", file_path)
        raise CVParseError(file_path, str(e)) from e
```

### Logging Guidelines

#### Structured Logging
```python
import logging

logger = logging.getLogger(__name__)

# ✅ Corretto - usa lazy formatting con %s
logger.info("Processing CV: '%s'", cv_id)
logger.debug("Found %d skills in section '%s'", len(skills), section_name)
logger.error("Failed to connect to Qdrant: '%s'", error_message)

# ❌ Evitare - f-string in log
logger.info(f"Processing CV: {cv_id}")
```

#### Log Levels
| Level | Uso |
|-------|-----|
| `DEBUG` | Dettagli tecnici per debugging |
| `INFO` | Eventi significativi (start/stop operazioni) |
| `WARNING` | Situazioni anomale ma gestibili |
| `ERROR` | Errori che richiedono attenzione |

---

## 3. FastAPI Guidelines

### Endpoint Structure
```python
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["search"])

class SkillSearchRequest(BaseModel):
    skills: list[str]
    limit: int = 10
    offset: int = 0

class ProfileMatch(BaseModel):
    cv_id: str
    score: float
    matched_skills: list[str]

@router.post(
    "/search/skills",
    response_model=list[ProfileMatch],
    status_code=status.HTTP_200_OK,
    summary="Cerca profili per skill",
    description="Restituisce profili che matchano le skill richieste.",
)
async def search_by_skills(request: SkillSearchRequest) -> list[ProfileMatch]:
    """Endpoint per ricerca profili per skill."""
    if not request.skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one skill is required",
        )
    return await skill_search_service.search(request)
```

### Dependency Injection
```python
from functools import lru_cache
from fastapi import Depends

@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Singleton per Qdrant client."""
    return QdrantClient(url=settings.QDRANT_URL)

@router.get("/health")
async def health_check(
    client: QdrantClient = Depends(get_qdrant_client),
) -> dict:
    return {"status": "ok", "qdrant": client.get_collections()}
```

### Response Models
```python
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """Response paginata standard."""
    items: list[T]
    total: int
    limit: int
    offset: int

class ErrorResponse(BaseModel):
    """Response di errore standard."""
    detail: str
    code: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

---

## 4. Qdrant Integration Guidelines

### Client Pattern (Singleton)
```python
from functools import lru_cache
from qdrant_client import QdrantClient

@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Return cached Qdrant client instance."""
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY")
    timeout = int(os.getenv("QDRANT_TIMEOUT", "10"))

    return QdrantClient(url=url, api_key=api_key, timeout=timeout)
```

### Collection Schema
```python
from qdrant_client import models

CV_SKILLS_SCHEMA = {
    "vectors_config": models.VectorParams(
        size=1536,  # OpenAI ada-002
        distance=models.Distance.COSINE,
    ),
    "payload_schema": {
        "cv_id": models.PayloadSchemaType.KEYWORD,
        "normalized_skills": models.PayloadSchemaType.KEYWORD,
        "skill_domain": models.PayloadSchemaType.KEYWORD,
        "seniority_bucket": models.PayloadSchemaType.KEYWORD,
    },
}
```

### Search Pattern
```python
async def search_by_skills(
    query_embedding: list[float],
    filters: SearchFilters,
    limit: int = 10,
) -> list[SearchResult]:
    """Cerca profili per embedding skill."""
    client = get_qdrant_client()

    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="skill_domain",
                match=models.MatchValue(value=filters.domain),
            ),
        ]
    ) if filters.domain else None

    results = client.search(
        collection_name="cv_skills",
        query_vector=query_embedding,
        query_filter=query_filter,
        limit=limit,
    )

    return [SearchResult.from_qdrant(r) for r in results]
```

---

## 5. Testing Guidelines

### Test Structure
```
tests/
├── conftest.py           # Fixtures comuni
├── fixtures/
│   └── sample_cvs/       # CV di test
├── unit/
│   ├── test_parser.py
│   └── test_skills.py
├── integration/
│   └── test_qdrant.py
└── e2e/
    └── test_api.py
```

### Test Naming Convention
```python
# Pattern: test_WHAT__WHEN__EXPECTED
def test_parse_cv__valid_docx__returns_parsed_cv():
    ...

def test_parse_cv__corrupted_file__raises_cv_parse_error():
    ...

def test_extract_skills__empty_text__returns_empty_list():
    ...
```

### Fixtures
```python
# conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def sample_cv_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_cvs" / "cv_standard.docx"

@pytest.fixture
def mock_qdrant_client(mocker):
    """Mock Qdrant client per test unitari."""
    return mocker.patch("src.services.qdrant.get_qdrant_client")
```

### Test Examples
```python
import pytest
from src.core.parser import parse_cv, CVParseError

class TestCVParser:
    """Test suite per CV parser."""

    def test_parse_cv__valid_docx__extracts_all_sections(self, sample_cv_path):
        # Arrange & Act
        result = parse_cv(sample_cv_path)

        # Assert
        assert result.metadata.cv_id is not None
        assert result.skills is not None
        assert len(result.experiences) > 0

    def test_parse_cv__missing_file__raises_error(self):
        with pytest.raises(CVParseError) as exc_info:
            parse_cv("/nonexistent/path.docx")

        assert "File not found" in str(exc_info.value)

    @pytest.mark.parametrize("encoding", ["utf-8", "latin-1", "cp1252"])
    def test_parse_cv__various_encodings__handles_gracefully(
        self, encoding, tmp_path
    ):
        # Test con diversi encoding
        ...
```

---

## 6. Code Quality Checklist

### Before Commit
- [ ] `make format` - Formatta il codice
- [ ] `make lint` - Verifica linting
- [ ] `make test` - Esegui test
- [ ] Type hints su tutte le funzioni pubbliche
- [ ] Docstring su classi e funzioni pubbliche

### Before PR
- [ ] `make preflight` - Tutti i check passano
- [ ] Coverage test ≥ 80% per nuovo codice
- [ ] Nessun TODO/FIXME lasciato
- [ ] Documentazione aggiornata se necessario
- [ ] OpenAPI spec aggiornata (se modifiche API)

---

## 7. Common Anti-Patterns to Avoid

### ❌ Evitare
```python
# Magic numbers
if score > 0.85:
    ...

# Hardcoded values
client = QdrantClient(url="http://localhost:6333")

# Broad exception handling
try:
    ...
except Exception:
    pass

# Mutable default arguments
def process(items: list = []):
    ...

# No type hints
def calculate(x, y):
    return x + y
```

### ✅ Preferire
```python
# Named constants
SKILL_MATCH_THRESHOLD = 0.85
if score > SKILL_MATCH_THRESHOLD:
    ...

# Environment variables
client = QdrantClient(url=os.getenv("QDRANT_URL"))

# Specific exception handling
try:
    ...
except ConnectionError as e:
    logger.error("Connection failed: '%s'", e)
    raise

# Immutable defaults
def process(items: list | None = None):
    items = items or []
    ...

# Type hints
def calculate(x: float, y: float) -> float:
    return x + y
```

---

## 8. Performance Guidelines

### Async Best Practices
```python
# ✅ Usa async per I/O bound operations
async def fetch_availability(cv_ids: list[str]) -> dict[str, Status]:
    async with httpx.AsyncClient() as client:
        tasks = [client.get(f"/status/{cv_id}") for cv_id in cv_ids]
        responses = await asyncio.gather(*tasks)
        return {cv_id: r.json() for cv_id, r in zip(cv_ids, responses)}

# ✅ Usa caching per operazioni costose
@lru_cache(maxsize=100)
def normalize_skill(raw_skill: str) -> str:
    ...
```

### Database/Vector Store
```python
# ✅ Batch operations
def index_cvs(cvs: list[ParsedCV]) -> None:
    points = [cv_to_point(cv) for cv in cvs]
    client.upsert(collection_name="cv_skills", points=points)

# ❌ Evitare N+1 queries
for cv in cvs:
    client.upsert(collection_name="cv_skills", points=[cv_to_point(cv)])
```

---

## 9. Security Guidelines

### Environment Variables
```python
# ✅ Mai hardcodare secrets
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not set")

# ✅ Usa pydantic-settings per configurazione
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    qdrant_url: str = "http://localhost:6333"

    model_config = {"env_file": ".env"}
```

### Input Validation
```python
# ✅ Valida sempre gli input
from pydantic import BaseModel, validator

class CVUploadRequest(BaseModel):
    file_name: str

    @validator("file_name")
    def validate_extension(cls, v):
        if not v.endswith(".docx"):
            raise ValueError("Only .docx files are supported")
        return v
```

### Logging Security
```python
# ❌ Mai loggare dati sensibili
logger.info(f"API Key: {api_key}")
logger.debug(f"User data: {user_pii}")

# ✅ Logga solo info necessarie
logger.info("Processing request for user_id: '%s'", user_id)
```

---

## 10. Review Checklist per Copilot

### Code Quality
- [ ] Type hints presenti e corretti
- [ ] Docstring su funzioni/classi pubbliche
- [ ] Nessun magic number
- [ ] Error handling appropriato
- [ ] Logging strutturato

### Architecture
- [ ] Rispetta la struttura a layer
- [ ] Separation of concerns
- [ ] Dependency injection usata correttamente
- [ ] Nessuna dipendenza ciclica

### Testing
- [ ] Test presenti per nuovo codice
- [ ] Test naming convention rispettata
- [ ] Fixtures appropriate
- [ ] Edge cases coperti

### Security
- [ ] Nessun secret hardcodato
- [ ] Input validation presente
- [ ] Nessun dato sensibile nei log

### Performance
- [ ] Async usato dove appropriato
- [ ] Batch operations per DB/vector store
- [ ] Caching implementato se necessario

---

## Quick Reference

### Comandi Makefile
```bash
make dev          # Setup ambiente dev
make lint         # Linting veloce
make lint-all     # Tutti i linter
make format       # Formatta codice
make test         # Esegui test
make test-cov     # Test con coverage
make preflight    # Check completo pre-commit
make run          # Avvia API
make docker-up    # Avvia Qdrant + Redis
```

### File Importanti
```
pyproject.toml          # Dipendenze e config tool
Makefile                # Automazione
.pre-commit-config.yaml # Pre-commit hooks
docker-compose.yml      # Services
.env.example            # Template variabili ambiente
```

---

> **Nota:** Queste linee guida sono vive e vengono aggiornate con l'evoluzione del progetto.
