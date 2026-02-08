# ProfileBot AI Agent Instructions

> **Scope:** Istruzioni per AI agent (Zed, Cursor, Windsurf) durante lo sviluppo di ProfileBot.

---

## Project Overview

**ProfileBot** è un sistema AI per il matching di profili professionali basato su competenze (skill-first approach).

### Tech Stack
- **Language**: Python 3.11+
- **Package Manager**: `uv`
- **Framework**: FastAPI
- **Validation**: Pydantic v2
- **Vector Store**: Qdrant
- **RAG**: Custom (Qdrant + OpenAI + retrieval + prompt)
- **Cache**: Redis
- **LLM**: OpenAI / Azure OpenAI
- **Testing**: pytest
- **Linting**: ruff, mypy, bandit
- **Formatting**: ruff

### Architecture (3 Layer)

```
src/
├── api/           # Layer 1: FastAPI endpoints, validation, routing
│   └── v1/        # Versioned API
├── core/          # Layer 2: Business logic
│   ├── parser/    # CV parsing
│   ├── skills/    # Skill extraction & normalization
│   ├── indexing/  # Embedding pipeline
│   └── llm/       # LLM integration
├── services/      # Layer 3: External services clients
│   ├── qdrant/    # Vector store
│   ├── embedding/ # Embedding generation
│   └── availability/ # Status service
└── utils/         # Utilities
```

**Data Flow:**
```
API Request → Validation → Core Logic → Services → External Systems
     ↓                         ↓            ↓
  Response  ←  Formatting  ←  Result  ←  Data
```

---

## Git Conventions

### Branch Naming
```
feature/US-XXX-descrizione-breve
bugfix/XXX-descrizione
hotfix/critical-fix
docs/update-readme
refactor/cleanup-module
```

### Commit Messages (Conventional Commits)
```
<type>(<scope>): <description>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Scopes:** `parser`, `skills`, `qdrant`, `api`, `llm`, `ci`

**Examples:**
```bash
feat(parser): add DOCX metadata extraction
fix(qdrant): handle connection timeout gracefully
test(skills): add normalization edge cases
```

---

## Python Code Standards

### Preflight Formalisms (make preflight)
- **Ruff check**: rispettare tutte le regole abilitate in `pyproject.toml` (nessuna eccezione locale non motivata).
- **Import ordering**: organizzare import in 3 blocchi (standard library, third-party, local) con una riga vuota tra i blocchi.
- **`__all__`**: se presente, deve essere **ordinato in stile isort** (alfabetico, case-sensitive) e definito come lista/tupla letterale.
- **Format**: il formato deve essere conforme a `ruff format --check` (niente formattazioni manuali divergenti).
- **Type hints**: obbligatori sulle funzioni pubbliche (mypy).
- **Logging**: usare lazy formatting con `%s`, mai f-string nei log (ruff).
- **Error handling**: usare eccezioni specifiche, no `except: pass` (ruff).
- **API lint**: `docs/openapi.yaml` deve esistere e passare `spectral lint`.

### Import Organization
```python
# 1. Standard library
from __future__ import annotations
import os
from datetime import datetime
from typing import Optional

# 2. Third-party
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 3. Local
from src.core.parser import parse_cv
from src.services.qdrant import get_qdrant_client
```

### Type Hints (OBBLIGATORI)
```python
# ✅ Corretto
def process_cv(file_path: str, options: ParseOptions | None = None) -> ParsedCV:
    ...

# ❌ Evitare
def process_cv(file_path, options=None):
    ...
```

### Docstrings (Google Style)
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
    """
```

### Logging (Lazy Formatting)
```python
import logging
logger = logging.getLogger(__name__)

# ✅ Corretto - usa %s
logger.info("Processing CV: '%s'", cv_id)
logger.debug("Found %d skills in section '%s'", len(skills), section_name)

# ❌ Evitare - f-string
logger.info(f"Processing CV: {cv_id}")
```

---

## FastAPI Patterns

### Endpoint Structure
```python
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["search"])

class SkillSearchRequest(BaseModel):
    """Request per ricerca profili."""
    skills: list[str]
    limit: int = 10

@router.post(
    "/search/skills",
    response_model=list[ProfileMatch],
    status_code=status.HTTP_200_OK,
    summary="Cerca profili per skill",
)
async def search_by_skills(
    request: SkillSearchRequest,
    client: QdrantClient = Depends(get_qdrant_client),
) -> list[ProfileMatch]:
    """Cerca profili che matchano le skill."""
    if not request.skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one skill is required",
        )
    return await perform_search(request, client)
```

### Dependency Injection (Singleton)
```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Return cached Qdrant client instance."""
    return QdrantClient(url=os.getenv("QDRANT_URL"))
```

---

## Error Handling

### Custom Exceptions
```python
# src/core/exceptions.py
class ProfileBotError(Exception):
    """Base exception per ProfileBot."""
    pass

class CVParseError(ProfileBotError):
    """Errore durante parsing CV."""
    def __init__(self, file_path: str, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Failed to parse '{file_path}': {reason}")

class SkillExtractionError(ProfileBotError):
    """Errore durante estrazione skill."""
    pass
```

### Exception Pattern
```python
def parse_cv(file_path: str) -> ParsedCV:
    try:
        return _do_parse(file_path)
    except FileNotFoundError:
        logger.error("CV file not found: '%s'", file_path)
        raise CVParseError(file_path, "File not found")
    except Exception as e:
        logger.exception("Unexpected error: '%s'", file_path)
        raise CVParseError(file_path, str(e)) from e
```

---

## Pydantic Models

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class CVMetadata(BaseModel):
    """Metadata CV."""
    cv_id: str = Field(..., description="ID univoco")
    file_name: str
    full_name: str | None = None
    parsed_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"frozen": True, "extra": "forbid"}

class SkillSearchRequest(BaseModel):
    skills: list[str]
    limit: int = 10

    @field_validator("skills")
    @classmethod
    def skills_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one skill required")
        return [s.strip().lower() for s in v if s.strip()]
```

---

## Testing Standards

### Test Naming Convention
```
test_WHAT__WHEN__EXPECTED
```

```python
def test_parse_cv__valid_docx__returns_all_sections():
    ...

def test_parse_cv__corrupted_file__raises_cv_parse_error():
    ...

def test_normalize_skill__exact_match__returns_confidence_1():
    ...
```

### Test Structure (AAA)
```python
def test_extract_skills__multiple_skills__returns_normalized_list():
    # Arrange
    text = "Python, FastAPI, PostgreSQL"
    dictionary = create_test_dictionary()

    # Act
    result = extract_skills(text, dictionary)

    # Assert
    assert len(result) == 3
    assert result[0].canonical == "python"
```

### Fixtures
```python
@pytest.fixture
def sample_cv_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_cvs" / "cv_standard.docx"

@pytest.fixture
def mock_qdrant_client(mocker):
    return mocker.patch("src.services.qdrant.get_qdrant_client")
```

---

## Anti-Patterns (EVITARE)

```python
# ❌ Magic numbers
if score > 0.85:

# ✅ Named constants
SKILL_MATCH_THRESHOLD = 0.85
if score > SKILL_MATCH_THRESHOLD:
```

```python
# ❌ Hardcoded values
client = QdrantClient(url="http://localhost:6333")

# ✅ Environment variables
client = QdrantClient(url=os.getenv("QDRANT_URL"))
```

```python
# ❌ Mutable default arguments
def process(items: list = []):

# ✅ None con inizializzazione
def process(items: list | None = None):
    items = items or []
```

```python
# ❌ Broad exception handling
except Exception:
    pass

# ✅ Specific handling
except ConnectionError as e:
    logger.error("Connection failed: '%s'", e)
    raise
```

```python
# ❌ f-string nei log
logger.info(f"Processing: {cv_id}")

# ✅ Lazy formatting
logger.info("Processing: '%s'", cv_id)
```

---

## Review Checklist

### Architettura
- [ ] Codice nel layer corretto (API/Core/Services)
- [ ] Nessuna business logic in API layer
- [ ] Single Responsibility rispettato

### Qualità Codice
- [ ] Type hints su funzioni pubbliche
- [ ] Docstring Google style
- [ ] Nessun magic number
- [ ] Import organizzati
- [ ] Metodi privati con `_` prefix

### Error Handling
- [ ] Custom exceptions (non generiche)
- [ ] Logging con `%s` (no f-string)
- [ ] No `except: pass`

### Testing
- [ ] Naming: `test_WHAT__WHEN__EXPECTED`
- [ ] AAA structure
- [ ] Coverage ≥ 80%

### Security
- [ ] No secrets hardcodati
- [ ] Environment variables
- [ ] No dati sensibili nei log

---

## Makefile Commands

```bash
make dev          # Setup ambiente dev
make lint         # Linting veloce
make format       # Formatta codice
make test         # Esegui test
make test-cov     # Test con coverage
make preflight    # Check completo pre-commit
make run          # Avvia API
make docker-up    # Avvia Qdrant + Redis
```

---

## Code Style - AI Agent Guidelines

> **alwaysApply: true** - Queste regole si applicano SEMPRE quando un AI agent genera codice.

### Comments
- **Don't** add comments that restate what code does
- **Don't** add JSDoc/docstrings unless required by the codebase (in questo progetto: solo su funzioni pubbliche)
- Only comment **why**, not **what**
- **No** "Added by Claude" or attribution comments
- **No** placeholder TODOs like `// TODO: implement`

### Don't Over-Engineer
- No helper functions for one-time operations
- No abstractions for single use cases
- No extra error handling "just in case"
- No backwards-compatibility shims when changing code directly works

### Stay Focused
- Only modify code relevant to the task
- No drive-by refactoring of unrelated code
- No reformatting lines you didn't change
- No adding type annotations where inference works (in questo progetto: type hints richiesti su funzioni pubbliche, opzionali su variabili locali)

---

## References

- [CONTRIBUTING.md](docs/CONTRIBUTING.md) - Git workflow
- [USER_STORIES_DETAILED.md](docs/USER_STORIES_DETAILED.md) - Specifiche US
- [.github/copilot_instructions.md](.github/copilot_instructions.md) - Linee guida estese
