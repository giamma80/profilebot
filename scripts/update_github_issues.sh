#!/bin/bash
# Script per aggiornare le GitHub issues con dettagli completi
# Esegui con: ./scripts/update_github_issues.sh
# Prerequisiti: gh auth login

set -e

echo "🔄 Aggiornamento GitHub Issues con specifiche dettagliate..."
echo ""

# US-002: Setup Qdrant Vector Store
echo "📝 Aggiornando US-002..."
gh issue edit 7 --body "**Come** data scientist
**Voglio** un'istanza Qdrant configurata
**Per** poter indicizzare e cercare i CV

## 🎯 Acceptance Criteria
- [ ] Qdrant running via docker-compose
- [ ] Collection \`cv_skills\` creata con schema corretto
- [ ] Collection \`cv_experiences\` creata con schema corretto
- [ ] Script di inizializzazione collections
- [ ] Script di test connessione
- [ ] Health check endpoint \`/health\` include Qdrant status

## 🔧 Technical Stack
- **Vector Store:** Qdrant (latest)
- **Client:** \`qdrant-client\` Python SDK
- **Container:** Docker Compose

## 📁 File da creare
\`\`\`
├── docker-compose.yml (add Qdrant service)
├── src/services/qdrant/
│   ├── __init__.py
│   ├── client.py          # Singleton client
│   ├── collections.py     # Schema definitions
│   └── health.py          # Health check
├── scripts/
│   └── init_qdrant.py     # Initialize collections
└── tests/
    └── test_qdrant_connection.py
\`\`\`

## 📐 Collection Schema - cv_skills
\`\`\`python
{
    \"vectors\": {\"size\": 1536, \"distance\": \"Cosine\"},
    \"payload_schema\": {
        \"cv_id\": \"keyword\",
        \"normalized_skills\": \"keyword[]\",
        \"skill_domain\": \"keyword\",
        \"seniority_bucket\": \"keyword\",
        \"dictionary_version\": \"keyword\"
    }
}
\`\`\`

## ✅ Definition of Done
- [ ] \`make docker-up\` avvia Qdrant
- [ ] Collections create con schema corretto
- [ ] \`/health\` endpoint include Qdrant status
- [ ] Test connessione passa in CI
- [ ] README aggiornato con setup Qdrant

## 🌿 Feature Branch
\`feature/US-002-qdrant-setup\`

**Story Points:** 5"

# US-003: Parser CV DOCX
echo "📝 Aggiornando US-003..."
gh issue edit 8 --body "**Come** sistema
**Voglio** estrarre testo strutturato dai CV in formato DOCX
**Per** poter processare i curriculum aziendali

## 🎯 Acceptance Criteria
- [ ] Parsing sezioni: Skills, Esperienze, Formazione, Certificazioni
- [ ] Estrazione metadata: nome, cognome, ruolo attuale
- [ ] Gestione errori per file malformati o corrotti
- [ ] Supporto encoding UTF-8 e caratteri speciali
- [ ] Unit test con almeno 5 CV di esempio
- [ ] Performance: < 2 sec per CV

## 🔧 Technical Stack
- **DOCX Parsing:** \`python-docx\`
- **Text Processing:** regex
- **Validation:** pydantic

## 📁 File da creare
\`\`\`
├── src/core/parser/
│   ├── __init__.py
│   ├── docx_parser.py     # Main parser
│   ├── section_detector.py
│   ├── metadata_extractor.py
│   └── schemas.py         # Pydantic models
├── tests/
│   ├── fixtures/
│   │   └── sample_cvs/    # 5+ sample CVs
│   └── test_cv_parser.py
└── docs/
    └── cv_format_guide.md
\`\`\`

## 📐 Output Schema
\`\`\`python
class ParsedCV(BaseModel):
    metadata: CVMetadata
    skills: SkillSection
    experiences: list[ExperienceItem]
    education: list[str]
    certifications: list[str]
    raw_text: str
\`\`\`

## ⚠️ Edge Cases da Gestire
- CV senza sezioni chiare
- Tabelle con skill
- File protetti da password
- Encoding non-UTF8

## ✅ Definition of Done
- [ ] Parser estrae tutte le sezioni
- [ ] Almeno 5 CV di test diversi
- [ ] Coverage test ≥ 80%
- [ ] Gestione errori documentata
- [ ] Performance validata (< 2 sec/CV)

## 🌿 Feature Branch
\`feature/US-003-cv-parser\`

**Story Points:** 8"

# US-004: Skill Extraction e Normalizzazione
echo "📝 Aggiornando US-004..."
gh issue edit 9 --body "**Come** data scientist
**Voglio** estrarre e normalizzare le skill dai CV
**Per** avere un vocabolario controllato di competenze

## 🎯 Acceptance Criteria
- [ ] Dizionario skill base con 100+ entry
- [ ] Mapping sinonimi → skill normalizzate
- [ ] Confidence score per ogni mapping (0.0-1.0)
- [ ] Log skill non riconosciute per review
- [ ] Categorizzazione skill per domain
- [ ] Versioning dizionario

## 🔧 Technical Stack
- **Matching:** \`rapidfuzz\` (fuzzy matching), regex
- **Storage:** YAML per dizionario

## 📁 File da creare
\`\`\`
├── src/core/skills/
│   ├── __init__.py
│   ├── extractor.py       # Main extraction logic
│   ├── normalizer.py      # Normalization engine
│   ├── dictionary.py      # Dictionary loader
│   └── schemas.py
├── data/
│   └── skills_dictionary.yaml
├── tests/
│   └── test_skill_extraction.py
└── scripts/
    └── analyze_unknown_skills.py
\`\`\`

## 📐 Dictionary Schema
\`\`\`yaml
version: \"1.0.0\"
skills:
  python:
    canonical: \"python\"
    domain: \"backend\"
    aliases: [\"py\", \"python3\"]
\`\`\`

## 🔄 Matching Strategy
1. Exact match (confidence: 1.0)
2. Alias match (confidence: 0.95)
3. Fuzzy match threshold 0.85
4. Unknown → log for review

## ✅ Definition of Done
- [ ] Dizionario con 100+ skill
- [ ] Mapping testato su 50+ skill reali
- [ ] Confidence score coerente
- [ ] Script report unknown skills
- [ ] Unit test per edge cases

## 🌿 Feature Branch
\`feature/US-004-skill-extraction\`

**Story Points:** 13"

# US-005: Embedding e Indexing Pipeline
echo "📝 Aggiornando US-005..."
gh issue edit 10 --body "**Come** sistema
**Voglio** generare embedding e indicizzare in Qdrant
**Per** abilitare la ricerca semantica

## 🎯 Acceptance Criteria
- [ ] Embedding con OpenAI text-embedding-ada-002 (o alternative)
- [ ] Upsert in collection \`cv_skills\` con payload completo
- [ ] Upsert in collection \`cv_experiences\` con payload completo
- [ ] Metadata completi su ogni punto
- [ ] Pipeline idempotente (re-run safe)
- [ ] Batch processing per performance

## 🔧 Technical Stack
- **Embedding:** OpenAI API / \`sentence-transformers\`
- **Vector Store:** Qdrant
- **Queue (optional):** Redis

## 📁 File da creare
\`\`\`
├── src/services/embedding/
│   ├── __init__.py
│   ├── embedder.py
│   ├── openai_client.py
│   └── local_embedder.py
├── src/core/indexing/
│   ├── __init__.py
│   ├── pipeline.py
│   ├── cv_indexer.py
│   └── batch_processor.py
├── scripts/
│   ├── index_single_cv.py
│   └── index_all_cvs.py
└── tests/
    └── test_indexing_pipeline.py
\`\`\`

## 📐 Pipeline Flow
\`\`\`
ParsedCV
    ├──► Skill Section ──► Embedding ──► cv_skills
    └──► Experience Items ──► Embedding ──► cv_experiences
\`\`\`

## 🔄 Idempotency Strategy
- Deterministic point ID: \`{cv_id}_{section}\`
- Upsert updates existing, inserts new

## ✅ Definition of Done
- [ ] Pipeline end-to-end funzionante
- [ ] Metadata completi su ogni punto
- [ ] Re-run non duplica dati
- [ ] Performance: < 5 sec per CV
- [ ] Test con 10+ CV reali

## 🌿 Feature Branch
\`feature/US-005-embedding-pipeline\`

**Story Points:** 13"

# US-006: API Ricerca Profili per Skill
echo "📝 Aggiornando US-006..."
gh issue edit 11 --body "**Come** utente
**Voglio** cercare profili in base a skill richieste
**Per** trovare candidati con competenze specifiche

## 🎯 Acceptance Criteria
- [ ] Endpoint \`POST /api/v1/search/skills\`
- [ ] Input: lista skill, filtri opzionali (seniority, domain)
- [ ] Output: lista profili ranked con score
- [ ] Paginazione risultati (limit, offset)
- [ ] Response time < 500ms
- [ ] OpenAPI documentation

## 🔧 Technical Stack
- **API:** FastAPI
- **Validation:** Pydantic
- **Docs:** OpenAPI 3.0

## 📁 File da creare
\`\`\`
├── src/api/
│   ├── __init__.py
│   ├── main.py
│   └── v1/
│       ├── router.py
│       ├── search.py
│       └── schemas.py
├── src/services/search/
│   ├── skill_search.py
│   └── scoring.py
└── tests/api/
    └── test_search_endpoints.py
\`\`\`

## 📐 Request/Response Schema
\`\`\`python
# Request
class SkillSearchRequest(BaseModel):
    skills: list[str]
    filters: Optional[SearchFilters]
    limit: int = 10
    offset: int = 0

# Response
class ProfileMatch(BaseModel):
    cv_id: str
    score: float
    matched_skills: list[str]
    missing_skills: list[str]
\`\`\`

## ✅ Definition of Done
- [ ] Endpoint funzionante e documentato
- [ ] Response < 500ms (testato)
- [ ] Paginazione corretta
- [ ] Test coverage ≥ 80%
- [ ] OpenAPI spec validata

## 🌿 Feature Branch
\`feature/US-006-search-api\`

**Story Points:** 8"

# US-007: Filtro Disponibilità
echo "📝 Aggiornando US-007..."
gh issue edit 12 --body "**Come** utente
**Voglio** filtrare i profili per stato di disponibilità
**Per** vedere solo candidati effettivamente assegnabili

## 🎯 Acceptance Criteria
- [ ] Filtri: \`only_free\`, \`free_or_partial\`, \`any\`
- [ ] Integrazione con source stato operativo (SharePoint/Excel)
- [ ] Cache stato con TTL configurabile
- [ ] Risposta esplicita se nessuno disponibile
- [ ] Aggiornamento stato asincrono

## 🔧 Technical Stack
- **Cache:** Redis
- **Data Source:** SharePoint List / Excel (inizialmente)
- **Scheduler:** APScheduler

## 📁 File da creare
\`\`\`
├── src/services/availability/
│   ├── __init__.py
│   ├── service.py
│   ├── cache.py
│   ├── source_sharepoint.py
│   └── source_excel.py
├── src/core/filters/
│   └── availability_filter.py
└── tests/
    └── test_availability_service.py
\`\`\`

## 📐 Availability States
\`\`\`python
class AvailabilityStatus(Enum):
    FREE = \"free\"           # Completamente disponibile
    PARTIAL = \"partial\"     # Allocato parzialmente
    BUSY = \"busy\"           # Allocato su progetto
    UNAVAILABLE = \"unavailable\"
\`\`\`

## 🔄 Cache Strategy
- Redis key: \`availability:{cv_id}\`
- TTL: 1 hour (configurable)

## ✅ Definition of Done
- [ ] Filtri funzionanti su tutti i modi
- [ ] Cache Redis operativa
- [ ] Refresh automatico configurato
- [ ] Messaggio esplicito se 0 risultati
- [ ] Test con dati mock

## 🌿 Feature Branch
\`feature/US-007-availability-filter\`

**Story Points:** 5"

# US-008: Match con Job Description
echo "📝 Aggiornando US-008..."
gh issue edit 13 --body "**Come** utente
**Voglio** trovare il miglior profilo per una job description
**Per** proporre candidati ad opportunità specifiche

## 🎯 Acceptance Criteria
- [ ] Endpoint \`POST /api/v1/match/job\`
- [ ] Input: testo job description (free text)
- [ ] Estrazione automatica skill richieste dalla JD
- [ ] Ranking profili con spiegazione LLM
- [ ] Output strutturato con motivazione per ogni match
- [ ] Distinzione tra must-have e nice-to-have skills

## 🔧 Technical Stack
- **LLM:** OpenAI GPT-4 / Azure OpenAI
- **Extraction:** LLM-based skill extraction
- **Ranking:** Vector similarity + LLM reasoning

## 📁 File da creare
\`\`\`
├── src/api/v1/
│   └── job_match.py
├── src/services/matching/
│   ├── job_analyzer.py
│   ├── candidate_ranker.py
│   └── explainer.py
├── src/core/llm/
│   ├── client.py
│   └── prompts.py
└── tests/
    └── test_job_matching.py
\`\`\`

## 📐 Flow
\`\`\`
Job Description
      │
      ▼
LLM Extraction ──► Required Skills
      │
      ▼
Vector Search ──► Candidate Shortlist (K=20)
      │
      ▼
Availability Filter ──► Filtered Candidates
      │
      ▼
LLM Ranking ──► Top N with Explanations
\`\`\`

## 🤖 LLM Parameters
- Model: GPT-4 / GPT-4-turbo
- Temperature: 0.1 (deterministic)
- Max tokens: 2000
- Response format: JSON mode

## ✅ Definition of Done
- [ ] Endpoint funzionante end-to-end
- [ ] Estrazione skill accurata (test su 5 JD)
- [ ] Spiegazioni coerenti e utili
- [ ] Response time < 10 sec
- [ ] Test con JD reali

## 🌿 Feature Branch
\`feature/US-008-job-match\`

**Story Points:** 13"

echo ""
echo "✅ Tutte le issues aggiornate!"
echo ""
echo "📋 Riepilogo:"
echo "  - US-002: Setup Qdrant Vector Store"
echo "  - US-003: Parser CV DOCX"
echo "  - US-004: Skill Extraction e Normalizzazione"
echo "  - US-005: Embedding e Indexing Pipeline"
echo "  - US-006: API Ricerca Profili per Skill"
echo "  - US-007: Filtro Disponibilità"
echo "  - US-008: Match con Job Description"
echo ""
echo "⚠️  Nota: I numeri delle issue (#7-#13) potrebbero variare."
echo "   Verifica i numeri corretti con: gh issue list"
