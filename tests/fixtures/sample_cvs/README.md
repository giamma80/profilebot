# Sample CVs per Testing

Questa directory contiene CV di esempio per i test del parser e della pipeline di embedding.

## Struttura Directory

```
tests/fixtures/sample_cvs/
├── README.md                          # Questo file
├── campione/                          # CV reali (CONFIDENZIALI - non committare)
│   └── curriculum_{res_id}.docx       # Formato legacy
├── 100000_marco_rossi.docx            # CV anonimi per test
├── 100001_luca_bianchi.docx
├── ...
└── cv_*.docx                          # CV legacy (senza res_id nel nome)
```

## CV Anonimi con `res_id` (Raccomandati)

I seguenti CV seguono la **naming convention richiesta** per US-013:

```
{res_id}_{nome}_{cognome}.docx
```

| File | res_id | Ruolo | Skills Principali |
|------|--------|-------|-------------------|
| `100000_marco_rossi.docx` | 100000 | Backend Developer - Python | Python, FastAPI, Django, PostgreSQL |
| `100001_luca_bianchi.docx` | 100001 | Frontend Developer - React | JavaScript, TypeScript, React, Next.js |
| `100002_giuseppe_ferrari.docx` | 100002 | Data Engineer - Spark | Python, Spark, Hadoop, Airflow |
| `100003_francesco_romano.docx` | 100003 | DevOps Engineer - AWS | AWS, Terraform, Docker, Kubernetes |
| `100004_alessandro_galli.docx` | 100004 | Full Stack Developer | Python, JavaScript, React, Node.js |
| `100005_andrea_costa.docx` | 100005 | ML Engineer - TensorFlow | Python, TensorFlow, PyTorch, Scikit-learn |
| `100006_matteo_fontana.docx` | 100006 | Java Developer - Spring | Java, Spring Boot, Hibernate, Maven |
| `100007_lorenzo_conti.docx` | 100007 | QA Engineer - Selenium | Python, Selenium, Cypress, Postman |
| `100008_davide_ricci.docx` | 100008 | Cloud Architect - Azure | Azure, Terraform, Docker, Kubernetes |
| `100009_simone_marino.docx` | 100009 | Scrum Master - Agile | Scrum, Kanban, JIRA, Confluence |

## Utilizzo nei Test

### 1. Test Parser con estrazione `res_id`

```python
import pytest
from pathlib import Path
from src.core.parser.docx_parser import parse_cv

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_cvs"

@pytest.fixture
def sample_cv_with_res_id():
    """CV con res_id nel filename."""
    return FIXTURES_DIR / "100000_marco_rossi.docx"

def test_parse_cv_extracts_res_id(sample_cv_with_res_id):
    """Verifica estrazione res_id dal filename."""
    parsed = parse_cv(sample_cv_with_res_id)

    assert parsed.metadata.res_id == 100000
    assert parsed.metadata.full_name == "Marco ROSSI"
    assert "BACKEND DEVELOPER" in parsed.metadata.current_role
```

### 2. Test Pipeline Embedding con `res_id`

```python
from src.core.embedding.pipeline import EmbeddingPipeline

def test_embedding_pipeline_includes_res_id(sample_cv_with_res_id, mock_qdrant):
    """Verifica che res_id sia incluso nei payload Qdrant."""
    parsed = parse_cv(sample_cv_with_res_id)
    skill_result = extract_skills(parsed)

    result = EmbeddingPipeline().process_cv(parsed, skill_result)

    # Verifica payload skills
    skills_payload = mock_qdrant.upsert_calls[0].payload
    assert skills_payload["res_id"] == 100000

    # Verifica payload experiences
    for exp_call in mock_qdrant.upsert_calls[1:]:
        assert exp_call.payload["res_id"] == 100000
```

### 3. Test Celery Tasks

```python
from src.services.embedding.tasks import embed_cv_task

def test_embed_cv_task_with_res_id(sample_cv_with_res_id, celery_app):
    """Test task Celery con res_id."""
    result = embed_cv_task.delay(
        res_id=100000,
        cv_path=str(sample_cv_with_res_id)
    )

    assert result.get(timeout=30)["res_id"] == 100000
```

### 4. Test Batch con Tutti i CV

```python
import glob

def get_all_test_cvs():
    """Recupera tutti i CV con naming convention corretta."""
    pattern = str(FIXTURES_DIR / "[0-9]*_*.docx")
    return glob.glob(pattern)

@pytest.mark.parametrize("cv_path", get_all_test_cvs())
def test_parse_all_cvs(cv_path):
    """Test parsing su tutti i CV anonimi."""
    parsed = parse_cv(cv_path)

    # Estrai res_id atteso dal filename
    filename = Path(cv_path).name
    expected_res_id = int(filename.split("_")[0])

    assert parsed.metadata.res_id == expected_res_id
    assert parsed.skills is not None
    assert len(parsed.experiences) > 0
```

## Naming Convention

### Formato Richiesto (US-013)
```
{res_id}_{nome}_{cognome}.docx
```

- `res_id`: Intero numerico (matricola risorsa)
- `nome`: Nome in lowercase
- `cognome`: Cognome in lowercase
- Separatore: underscore `_`

### Esempi Validi
- `100000_marco_rossi.docx` ✅
- `12345_anna_verdi.docx` ✅
- `99999_a_b.docx` ✅

### Esempi Non Validi
- `cv_mario_rossi.docx` ❌ (manca res_id numerico)
- `marco_rossi.docx` ❌ (manca res_id)
- `100000-marco-rossi.docx` ❌ (separatore errato)

## Struttura CV

Ogni CV anonimo contiene:

1. **Header**
   - Nome completo
   - Ruolo attuale
   - Anni di esperienza
   - Data ultimo aggiornamento

2. **COMPETENZE**
   - Linguaggi & Framework
   - Tools & Platform
   - Metodologie

3. **ESPERIENZA PROFESSIONALE**
   - 2-3 esperienze lavorative
   - Date, azienda, ruolo
   - Descrizione attività
   - Strumenti utilizzati

4. **ISTRUZIONE**
   - Laurea
   - Università
   - Date

5. **LINGUE**
   - Italiano (madrelingua)
   - Inglese (livello variabile)

## Note

- I CV nella cartella `campione/` sono **CONFIDENZIALI** e non devono essere committati
- Aggiungere `campione/` al `.gitignore` se non già presente
- I CV anonimi (100000-100009) possono essere committati liberamente
- Per aggiungere nuovi CV di test, seguire la naming convention `{res_id}_{nome}_{cognome}.docx`
