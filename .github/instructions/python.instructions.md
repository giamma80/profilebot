---
applyTo: "**/*.py"
---

# ProfileBot Python Code Review Guidelines

Queste linee guida si applicano a tutto il codice Python del progetto ProfileBot. Forniscono pattern architetturali, principi di design e best practices per garantire qualità e manutenibilità del codice.

---

## 🏗️ Architettura del Progetto

### Struttura a Layer

ProfileBot segue un'architettura a 3 layer. Assicurarsi che il codice appartenga al layer corretto:

**Layer 1: API** (`src/api/`)
- Endpoint FastAPI, validazione input, routing
- Non contiene business logic complessa

**Layer 2: Core** (`src/core/`)
- Business logic: parsing, skill extraction, indexing, LLM
- Logica di dominio, trasformazioni dati

**Layer 3: Services** (`src/services/`)
- Comunicazione con servizi esterni: Qdrant, Redis, OpenAI
- Client wrapper, health check, connection pooling

### Flusso Dati

```
API Request → Validation → Core Logic → Services → External Systems
     ↓                         ↓            ↓
  Response  ←  Formatting  ←  Result  ←  Data
```

---

## 📋 Standard API Design

### FastAPI Endpoint Pattern

```python
# ✅ Good: Endpoint strutturato correttamente
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["search"])

class SkillSearchRequest(BaseModel):
    """Request per ricerca profili per skill."""
    skills: list[str]
    limit: int = 10
    offset: int = 0

class ProfileMatch(BaseModel):
    """Singolo match di profilo."""
    cv_id: str
    score: float
    matched_skills: list[str]

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
    """Cerca profili che matchano le skill richieste."""
    if not request.skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one skill is required",
        )
    return await perform_search(request, client)


# ❌ Bad: Endpoint senza struttura
@router.post("/search")
def search(data: dict):  # No type hints, no validation
    return do_search(data)
```

### Dependency Injection

```python
# ✅ Good: Singleton con caching
from functools import lru_cache

@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Return cached Qdrant client instance."""
    return QdrantClient(url=os.getenv("QDRANT_URL"))

@router.get("/health")
async def health(client: QdrantClient = Depends(get_qdrant_client)):
    return {"status": "ok"}


# ❌ Bad: Client creato ad ogni richiesta
@router.get("/health")
async def health():
    client = QdrantClient(url="http://localhost:6333")  # Nuovo client ogni volta!
    return {"status": "ok"}
```

---

## 🧱 Code Structure Guidelines

### Import Organization

**Regola**: Importare moduli, non nomi. Eccezioni: `typing` e tipi comuni.

```python
# ✅ Good: Import organizzati correttamente
from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

from src.core.parser import parse_cv
from src.services.qdrant import get_qdrant_client


# ❌ Bad: Import disordinati e nomi diretti
from qdrant_client.models import Distance, VectorParams  # Preferire: from qdrant_client import models
from src.core.parser.docx_parser import DOCXParser, parse_cv, CVParseError  # Troppi nomi
import os, sys, logging  # Mai su una riga
```

### Access Control

```python
# ✅ Good: Metodi privati per uso interno
class CVParser:
    """Parser per CV in formato DOCX."""

    def parse(self, file_path: str) -> ParsedCV:
        """Public API - entry point."""
        content = self._extract_content(file_path)
        sections = self._detect_sections(content)
        return self._build_result(sections)

    def _extract_content(self, file_path: str) -> str:
        """Private - solo uso interno."""
        pass

    def _detect_sections(self, content: str) -> dict:
        """Private - solo uso interno."""
        pass

    def _build_result(self, sections: dict) -> ParsedCV:
        """Private - solo uso interno."""
        pass


# ❌ Bad: Tutti i metodi pubblici
class CVParser:
    def parse(self, file_path: str) -> ParsedCV:
        content = self.extract_content(file_path)  # Dovrebbe essere privato
        sections = self.detect_sections(content)   # Dovrebbe essere privato
        return self.build_result(sections)         # Dovrebbe essere privato

    def extract_content(self, file_path: str) -> str:  # Mai chiamato esternamente!
        pass
```

### Single Responsibility Principle

```python
# ✅ Good: Moduli focalizzati su una responsabilità
# src/core/parser/docx_parser.py - Solo parsing DOCX
class DOCXParser:
    """Estrae testo da file DOCX."""
    pass

# src/core/parser/section_detector.py - Solo detection sezioni
class SectionDetector:
    """Identifica sezioni nel testo del CV."""
    pass

# src/core/skills/normalizer.py - Solo normalizzazione
class SkillNormalizer:
    """Normalizza skill su dizionario controllato."""
    pass


# ❌ Bad: Modulo monolitico con responsabilità multiple
# utils.py - Tutto dentro!
class CVParser: ...
class SkillExtractor: ...
class QdrantHelper: ...
def format_date(...): ...
def clean_text(...): ...
```

---

## 🛡️ Error Handling

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

class QdrantConnectionError(ProfileBotError):
    """Errore connessione Qdrant."""
    pass
```

### Exception Handling Pattern

```python
# ✅ Good: Gestione specifica delle eccezioni
import logging

logger = logging.getLogger(__name__)

def parse_cv(file_path: str) -> ParsedCV:
    try:
        return _do_parse(file_path)
    except FileNotFoundError:
        logger.error("CV file not found: '%s'", file_path)
        raise CVParseError(file_path, "File not found")
    except PermissionError:
        logger.error("Permission denied for file: '%s'", file_path)
        raise CVParseError(file_path, "Permission denied")
    except Exception as e:
        logger.exception("Unexpected error parsing: '%s'", file_path)
        raise CVParseError(file_path, str(e)) from e


# ❌ Bad: Eccezioni generiche o silenziate
def parse_cv(file_path: str) -> ParsedCV:
    try:
        return _do_parse(file_path)
    except Exception:
        pass  # Errore silenzioso!

    try:
        return _do_parse(file_path)
    except:  # Bare except!
        raise Exception("Error")  # Eccezione generica
```

---

## 📝 Type Hints e Documentazione

### Type Hints Obbligatori

```python
# ✅ Good: Type hints completi
from typing import Optional
from datetime import datetime

def extract_skills(
    text: str,
    dictionary: SkillDictionary,
    threshold: float = 0.85,
) -> list[NormalizedSkill]:
    """Estrae skill dal testo."""
    pass

def search_profiles(
    query_embedding: list[float],
    filters: SearchFilters | None = None,
    limit: int = 10,
) -> list[ProfileMatch]:
    """Cerca profili per embedding."""
    pass


# ❌ Bad: Type hints mancanti
def extract_skills(text, dictionary, threshold=0.85):
    pass

def search_profiles(query_embedding, filters=None, limit=10):
    pass
```

### Docstring (Google Style)

```python
def normalize_skill(
    raw_skill: str,
    dictionary: SkillDictionary,
) -> NormalizedSkill:
    """Normalizza una skill grezza usando il dizionario.

    Cerca match esatto, alias, e fuzzy matching in ordine.
    Se non trova match, logga la skill come unknown.

    Args:
        raw_skill: Skill grezza da normalizzare (es. "Python 3.x").
        dictionary: Dizionario delle skill normalizzate.

    Returns:
        NormalizedSkill con canonical name e confidence score.

    Raises:
        SkillExtractionError: Se raw_skill è vuoto o None.

    Example:
        >>> skill = normalize_skill("py", dictionary)
        >>> skill.canonical
        'python'
        >>> skill.confidence
        0.95
    """
```

---

## 🔍 Logging Guidelines

### Structured Logging

```python
import logging

logger = logging.getLogger(__name__)

# ✅ Good: Lazy formatting con %s, valori tra apici
logger.info("Processing CV: '%s'", cv_id)
logger.debug("Found %d skills in section '%s'", len(skills), section_name)
logger.warning("Skill not found in dictionary: '%s'", unknown_skill)
logger.error("Failed to connect to Qdrant: '%s'", error_message)

# ❌ Bad: f-string nei log (valutate sempre)
logger.info(f"Processing CV: {cv_id}")
logger.debug(f"Found {len(skills)} skills")
```

### Log Levels

| Level | Uso |
|-------|-----|
| `DEBUG` | Dettagli tecnici, variabili interne |
| `INFO` | Eventi significativi (inizio/fine operazioni) |
| `WARNING` | Situazioni anomale ma gestibili |
| `ERROR` | Errori che richiedono attenzione |

---

## 🧪 Testing Standards

### Test Naming Convention

```
test_WHAT__WHEN__EXPECTED
```

```python
# ✅ Good: Nomi descrittivi
def test_parse_cv__valid_docx__returns_all_sections():
    pass

def test_parse_cv__corrupted_file__raises_cv_parse_error():
    pass

def test_normalize_skill__exact_match__returns_confidence_1():
    pass

def test_search_profiles__empty_query__returns_empty_list():
    pass


# ❌ Bad: Nomi generici
def test_parser():
    pass

def test_search():
    pass

def test_it_works():
    pass
```

### Test Structure (Arrange-Act-Assert)

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
    assert all(s.confidence >= 0.85 for s in result)
```

### Fixtures

```python
# conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def sample_cv_path() -> Path:
    """Path a CV di esempio."""
    return Path(__file__).parent / "fixtures" / "sample_cvs" / "cv_standard.docx"

@pytest.fixture
def skill_dictionary() -> SkillDictionary:
    """Dizionario skill per test."""
    return SkillDictionary.from_yaml("tests/fixtures/skills_test.yaml")

@pytest.fixture
def mock_qdrant_client(mocker):
    """Mock Qdrant client."""
    return mocker.patch("src.services.qdrant.get_qdrant_client")
```

---

## 🚫 Anti-Pattern da Evitare

### Code Smells

```python
# ❌ Magic numbers
if score > 0.85:
    pass
if len(results) > 50:
    pass

# ✅ Usare costanti
SKILL_MATCH_THRESHOLD = 0.85
MAX_SEARCH_RESULTS = 50

if score > SKILL_MATCH_THRESHOLD:
    pass
if len(results) > MAX_SEARCH_RESULTS:
    pass
```

```python
# ❌ Hardcoded values
client = QdrantClient(url="http://localhost:6333")
api_key = "sk-12345"

# ✅ Environment variables
client = QdrantClient(url=os.getenv("QDRANT_URL"))
api_key = os.getenv("OPENAI_API_KEY")
```

```python
# ❌ Mutable default arguments
def process(items: list = []):
    items.append("new")
    return items

# ✅ None con inizializzazione
def process(items: list | None = None):
    items = items or []
    items.append("new")
    return items
```

```python
# ❌ Broad exception handling
try:
    do_something()
except Exception:
    pass

# ✅ Specific exception handling
try:
    do_something()
except ConnectionError as e:
    logger.error("Connection failed: '%s'", e)
    raise
```

---

## 🔄 Pydantic Model Guidelines

### Model Definition

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CVMetadata(BaseModel):
    """Metadata estratti dal CV."""

    cv_id: str = Field(..., description="ID univoco del CV")
    file_name: str = Field(..., description="Nome file originale")
    full_name: Optional[str] = Field(None, description="Nome completo")
    current_role: Optional[str] = Field(None, description="Ruolo attuale")
    parsed_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "frozen": True,  # Immutabile
        "extra": "forbid",  # No campi extra
    }


class NormalizedSkill(BaseModel):
    """Skill normalizzata."""

    original: str = Field(..., description="Skill originale")
    canonical: str = Field(..., description="Nome canonico")
    domain: str = Field(..., description="Dominio (backend, frontend, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Score confidenza")
    match_type: str = Field(..., description="Tipo match (exact, alias, fuzzy)")
```

### Validation

```python
from pydantic import BaseModel, field_validator

class SkillSearchRequest(BaseModel):
    skills: list[str]
    limit: int = 10

    @field_validator("skills")
    @classmethod
    def skills_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one skill is required")
        return [s.strip().lower() for s in v if s.strip()]

    @field_validator("limit")
    @classmethod
    def limit_range(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("Limit must be between 1 and 100")
        return v
```

---

## ✅ Review Checklist

### Architettura
- [ ] Il codice appartiene al layer corretto (API/Core/Services)
- [ ] Nessuna business logic complessa nel layer API
- [ ] Single Responsibility: un modulo, una responsabilità
- [ ] Dependency injection per servizi esterni (Qdrant, Redis, OpenAI)
- [ ] Flusso dati chiaro e coerente
- [ ] Moduli organizzati per funzionalità (parser, normalizer, search, etc.)
- [ ] Nessun modulo monolitico con responsabilità multiple
- [ ] Nessun codice duplicato (DRY)
- [ ] Nessun import circolare
- [ ] Nessun modulo con più di 300 righe (se sì, valutare refactoring)
- [ ] Nessun metodo con più di 50 righe (se sì, valutare refactoring)
- [ ] Nessun metodo con più di 5 parametri (se sì, valutare refactoring)
- [ ] Nessun metodo che fa più di una cosa (es. parsing + normalizzazione + logging)
- [ ] Nessun modulo che importa direttamente un modulo di layer superiore (es. core che importa api)

### Qualità Codice
- [ ] Type hints su tutte le funzioni pubbliche
- [ ] Docstring su classi e funzioni pubbliche (Google style)
- [ ] Nessun magic number/string
- [ ] Import organizzati (stdlib → third-party → local)
- [ ] Metodi privati con prefisso `_` se uso interno
- [ ] Ricordati tutte le regole ruff segnalate in fase di linting https://docs.astral.sh/ruff/rules/#pyupgrade-up
- [ ] Nessun mutable default argument (es. `def func(items: list = [])`)
- [ ] Nessun hardcoded value (es. URL, API key, costanti) senza env var o costante definita


### Error Handling
- [ ] Eccezioni custom specifiche (non generiche)
- [ ] Logging strutturato con `%s` (no f-string)
- [ ] Nessun `except: pass` o `except Exception: pass`

### Testing
- [ ] Test naming: `test_WHAT__WHEN__EXPECTED`
- [ ] Arrange-Act-Assert structure
- [ ] Fixtures per dati comuni
- [ ] Coverage ≥ 80% per nuovo codice

### Security
- [ ] Nessun secret hardcodato
- [ ] Environment variables per configurazione
- [ ] Nessun dato sensibile nei log

---

## 📚 References

- [CONTRIBUTING.md](../../docs/CONTRIBUTING.md) - Git workflow e convenzioni
- [copilot_instructions.md](../copilot_instructions.md) - Linee guida generali
- [USER_STORIES_DETAILED.md](../../docs/USER_STORIES_DETAILED.md) - Specifiche tecniche US
