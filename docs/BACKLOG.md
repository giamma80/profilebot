# Product Backlog - ProfileBot MVP

## Epic 1: Infrastructure Setup
> Configurazione ambiente e infrastruttura base

### US-001: Setup Repository e CI/CD
**Come** sviluppatore
**Voglio** un repository Git configurato con CI/CD
**Per** poter collaborare e deployare in modo automatizzato

**Acceptance Criteria:**
- [ ] Repository GitHub creato
- [ ] Branch protection su main
- [ ] GitHub Actions per test e lint
- [ ] Pre-commit hooks configurati

**Story Points:** 3
**Priority:** P0 - Critical

---

### US-002: Setup Qdrant Vector Store
**Come** data scientist
**Voglio** un'istanza Qdrant configurata
**Per** poter indicizzare e cercare i CV

**Acceptance Criteria:**
- [ ] Qdrant running (docker-compose)
- [ ] Collection `cv_skills` creata
- [ ] Collection `cv_experiences` creata
- [ ] Script di test connessione

**Story Points:** 5
**Priority:** P0 - Critical

---

## Epic 2: Document Ingestion
> Pipeline per processare e indicizzare i CV

### US-003: Parser CV DOCX
**Come** sistema
**Voglio** estrarre testo strutturato dai CV in formato DOCX
**Per** poter processare i curriculum aziendali

**Acceptance Criteria:**
- [ ] Parsing sezioni (skill, esperienze, formazione)
- [ ] Estrazione metadata (nome, ruolo)
- [ ] Gestione errori per file malformati
- [ ] Unit test con CV di esempio

**Story Points:** 8
**Priority:** P0 - Critical

---

### US-004: Skill Extraction e Normalizzazione
**Come** data scientist
**Voglio** estrarre e normalizzare le skill dai CV
**Per** avere un vocabolario controllato di competenze

**Acceptance Criteria:**
- [ ] Dizionario skill base (100+ entry)
- [ ] Mapping sinonimi → skill normalizzate
- [ ] Confidence score per ogni mapping
- [ ] Log skill non riconosciute

**Story Points:** 13
**Priority:** P0 - Critical

---

### US-005: Embedding e Indexing Pipeline
**Come** sistema
**Voglio** generare embedding e indicizzare in Qdrant
**Per** abilitare la ricerca semantica

**Acceptance Criteria:**
- [ ] Embedding con OpenAI/sentence-transformers
- [ ] Upsert in cv_skills collection
- [ ] Upsert in cv_experiences collection
- [ ] Metadata completi (cv_id, section_type, etc.)
- [ ] Pipeline idempotente

**Story Points:** 13
**Priority:** P0 - Critical

---

## Epic 3: Search & Matching
> Funzionalità di ricerca e matching profili

### US-006: API Ricerca Profili per Skill
**Come** utente
**Voglio** cercare profili in base a skill richieste
**Per** trovare candidati con competenze specifiche

**Acceptance Criteria:**
- [ ] Endpoint POST /api/search/skills
- [ ] Input: lista skill, filtri (seniority, domain)
- [ ] Output: lista profili ranked con score
- [ ] Paginazione risultati

**Story Points:** 8
**Priority:** P1 - High

---

### US-007: Filtro Disponibilità
**Come** utente
**Voglio** filtrare i profili per stato di disponibilità
**Per** vedere solo candidati effettivamente assegnabili

**Acceptance Criteria:**
- [ ] Filtri: only_free, free_or_partial, any
- [ ] Integrazione con source stato operativo
- [ ] Cache stato con TTL
- [ ] Risposta esplicita se nessuno disponibile

**Story Points:** 5
**Priority:** P1 - High

---

### US-008: Match con Job Description
**Come** utente
**Voglio** trovare il miglior profilo per una job description
**Per** proporre candidati ad opportunità specifiche

**Acceptance Criteria:**
- [ ] Endpoint POST /api/match/job
- [ ] Input: testo job description
- [ ] Estrazione automatica skill richieste
- [ ] Ranking profili con spiegazione LLM
- [ ] Output strutturato con motivazione

**Story Points:** 13
**Priority:** P1 - High

---

## Epic 4: LLM Integration
> Integrazione con modelli linguistici per decisioni spiegate

### US-009: LLM Decision Engine
**Come** sistema
**Voglio** usare un LLM per decisioni di matching spiegate
**Per** fornire risposte comprensibili e motivate

**Acceptance Criteria:**
- [ ] Integrazione OpenAI/Azure OpenAI
- [ ] System prompt ottimizzato skill-first
- [ ] Context normalization per CV
- [ ] Output con cv_id + decision_reason
- [ ] Temperature bassa (0.0-0.3)

**Story Points:** 8
**Priority:** P1 - High

---

### US-010: Source Attribution
**Come** utente
**Voglio** sapere da dove viene ogni affermazione del sistema
**Per** verificare e fidarmi delle raccomandazioni

**Acceptance Criteria:**
- [ ] Riferimento a CV_ID per ogni claim
- [ ] Sezione (skill/experience) citata
- [ ] Log tracciabile per audit

**Story Points:** 5
**Priority:** P2 - Medium

---

## Epic 5: User Interface
> Interfaccia utente per interazione con il sistema

### US-011: Chat Interface Base
**Come** utente
**Voglio** un'interfaccia chat semplice
**Per** interagire con il sistema in linguaggio naturale

**Acceptance Criteria:**
- [ ] Input testuale
- [ ] Visualizzazione risposta formattata
- [ ] Storico conversazione
- [ ] Responsive design

**Story Points:** 8
**Priority:** P2 - Medium

---

### US-012: Visualizzazione Profili
**Come** utente
**Voglio** vedere i dettagli dei profili suggeriti
**Per** valutare i candidati proposti

**Acceptance Criteria:**
- [ ] Card profilo con skill
- [ ] Badge disponibilità
- [ ] Esperienze rilevanti
- [ ] Link a CV completo

**Story Points:** 5
**Priority:** P2 - Medium

---

## Epic 6: Operations
> Monitoring, logging e manutenzione

### US-013: Logging e Monitoring
**Come** ops engineer
**Voglio** log strutturati e metriche
**Per** monitorare la salute del sistema

**Acceptance Criteria:**
- [ ] Structured logging (JSON)
- [ ] Metriche latenza API
- [ ] Metriche utilizzo Qdrant
- [ ] Health check endpoint

**Story Points:** 5
**Priority:** P3 - Low

---

## Sprint Planning MVP

### Sprint 1 (2 settimane)
- US-001: Setup Repository ✓
- US-002: Setup Qdrant
- US-003: Parser CV DOCX

### Sprint 2 (2 settimane)
- US-004: Skill Extraction
- US-005: Embedding Pipeline

### Sprint 3 (2 settimane)
- US-006: API Ricerca Skill
- US-007: Filtro Disponibilità

### Sprint 4 (2 settimane)
- US-008: Match Job Description
- US-009: LLM Decision Engine

### Sprint 5 (2 settimane)
- US-010: Source Attribution
- US-011: Chat Interface
- US-012: Visualizzazione Profili

---

## Story Points Summary

| Priority | Stories | Total Points |
|----------|---------|--------------|
| P0 - Critical | 5 | 42 |
| P1 - High | 4 | 34 |
| P2 - Medium | 3 | 18 |
| P3 - Low | 1 | 5 |
| **Total** | **13** | **99** |

**Velocity stimata:** 20 SP/sprint
**MVP completabile in:** ~5 sprint (10 settimane)
