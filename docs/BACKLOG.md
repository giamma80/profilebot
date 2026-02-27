# Product Backlog - ProfileBot MVP

> **Ultimo aggiornamento:** 27 febbraio 2026

## Epic 1: Infrastructure Setup
> Configurazione ambiente e infrastruttura base

### US-001: Setup Repository e CI/CD ✅
**Come** sviluppatore
**Voglio** un repository Git configurato con CI/CD
**Per** poter collaborare e deployare in modo automatizzato

**Acceptance Criteria:**
- [x] Repository GitHub creato
- [x] Branch protection su master
- [x] GitHub Actions per test e lint
- [x] Pre-commit hooks configurati

**Story Points:** 3
**Priority:** P0 - Critical
**Status:** ✅ Completata (Sprint 1)

---

### US-002: Setup Qdrant Vector Store ✅
**Come** data scientist
**Voglio** un'istanza Qdrant configurata
**Per** poter indicizzare e cercare i CV

**Acceptance Criteria:**
- [x] Qdrant running (docker-compose)
- [x] Collection `cv_skills` creata
- [x] Collection `cv_experiences` creata
- [x] Script di test connessione

**Story Points:** 5
**Priority:** P0 - Critical
**Status:** ✅ Completata (Sprint 1)

---

## Epic 2: Document Ingestion
> Pipeline per processare e indicizzare i CV

### US-003: Parser CV DOCX ✅
**Come** sistema
**Voglio** estrarre testo strutturato dai CV in formato DOCX
**Per** poter processare i curriculum aziendali

**Acceptance Criteria:**
- [x] Parsing sezioni (skill, esperienze, formazione)
- [x] Estrazione metadata (nome, ruolo)
- [x] Gestione errori per file malformati
- [x] Unit test con CV di esempio

**Story Points:** 8
**Priority:** P0 - Critical
**Status:** ✅ Completata (Sprint 1)

---

### US-004: Skill Extraction e Normalizzazione ✅
**Come** data scientist
**Voglio** estrarre e normalizzare le skill dai CV
**Per** avere un vocabolario controllato di competenze

**Acceptance Criteria:**
- [x] Dizionario skill base (100+ entry)
- [x] Mapping sinonimi → skill normalizzate
- [x] Confidence score per ogni mapping
- [x] Log skill non riconosciute

**Story Points:** 13
**Priority:** P0 - Critical
**Status:** ✅ Completata (Sprint 2)

---

### US-005: Embedding e Indexing Pipeline ✅
**Come** sistema
**Voglio** generare embedding e indicizzare in Qdrant
**Per** abilitare la ricerca semantica

**Acceptance Criteria:**
- [x] Embedding con OpenAI/sentence-transformers
- [x] Upsert in cv_skills collection
- [x] Upsert in cv_experiences collection
- [x] Metadata completi (cv_id, section_type, etc.)
- [x] Pipeline idempotente

**Story Points:** 13
**Priority:** P0 - Critical
**Status:** ✅ Completata (Sprint 2)

---

### US-013: Celery Job Queue e API Endpoints ✅
**Come** sistema
**Voglio** una coda di job asincroni per la pipeline di embedding
**Per** gestire carichi di lavoro pesanti senza bloccare le API

**Acceptance Criteria:**
- [x] Celery worker configurato
- [x] Task per embedding singolo e batch
- [x] API endpoints per trigger e status
- [x] Celery Beat per scheduling

**Story Points:** 8
**Priority:** P0 - Critical
**Status:** ✅ Completata (Sprint 2/3)

---

### US-016: Orchestrazione Ingestion Scraper (DAG config) ✅
**Come** sistema
**Voglio** definire un workflow dichiarativo per le sorgenti scraper
**Per** aggiungere nuove fonti senza modificare l'orchestrazione

**Acceptance Criteria:**
- [x] Workflow definito in JSON/YAML con nodi e dipendenze
- [x] Loader con validazione schema (Pydantic)
- [x] Runner che converte il DAG in primitive Celery
- [x] Fan-out su res_id da cache Redis
- [x] Mapping nodi → task Celery esistenti

**Story Points:** 5
**Priority:** P2 - Medium
**Status:** ✅ Completata (Sprint 4)

---

## Epic 3: Search & Matching
> Funzionalità di ricerca e matching profili

### US-006: API Ricerca Profili per Skill ✅
**Come** utente
**Voglio** cercare profili in base a skill richieste
**Per** trovare candidati con competenze specifiche

**Acceptance Criteria:**
- [x] Endpoint POST /api/search/skills
- [x] Input: lista skill, filtri (seniority, domain)
- [x] Output: lista profili ranked con score
- [x] Paginazione risultati

**Story Points:** 8
**Priority:** P1 - High
**Status:** ✅ Completata (Sprint 3)

---

### US-007: Filtro Disponibilità (Availability Service) ✅
**Come** utente
**Voglio** filtrare i profili per stato di disponibilità
**Per** vedere solo candidati effettivamente assegnabili

**Acceptance Criteria:**
- [x] Filtri: only_free, free_or_partial, any
- [x] Connector Pattern per fonti esterne (SharePoint)
- [x] Cache stato con TTL su Redis
- [x] Risposta esplicita se nessuno disponibile
- [x] API REST per load, stats, refresh, task monitoring

**Story Points:** 5
**Priority:** P1 - High
**Status:** ✅ Completata (Sprint 3)

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
**Status:** ⏳ Sprint 4 — dipende da US-009

---

## Epic 4: LLM Integration
> Integrazione con modelli linguistici per decisioni spiegate

### US-009: LLM Decision Engine ✅
**Come** sistema
**Voglio** usare un LLM per decisioni di matching spiegate
**Per** fornire risposte comprensibili e motivate

**Acceptance Criteria:**
- [x] Integrazione OpenAI/Azure OpenAI/Ollama (client wrapper con retry)
- [x] System prompt ottimizzato skill-first
- [x] Context normalization per CV (max 5-7 profili)
- [x] Output strutturato con cv_id + decision_reason (JSON mode)
- [x] Temperature bassa (0.0-0.3) configurabile
- [x] Settings LLM centralizzati in config.py

**Story Points:** 8
**Priority:** P1 - High
**Status:** ✅ Completata (Sprint 4)

---

### US-009.1: Seniority Calculator
**Come** sistema
**Voglio** calcolare il seniority_bucket in base a esperienze e skill
**Per** sbloccare il campo oggi hardcoded a "unknown" nel KP

**Acceptance Criteria:**
- [ ] Euristica basata su years_experience + skill count + ruolo
- [ ] Integrazione in EmbeddingPipeline (rimuovere hardcode "unknown")
- [ ] Test con profili di diverse seniority
- [ ] Payload Qdrant aggiornato con valore calcolato

**Story Points:** 2
**Priority:** P1 - High
**Status:** 🔜 Sprint 5
**Ref:** LLM-study.md §3.4, §12.1 gap #2

---

### US-009.2: Reskilling Infrastructure
**Come** sistema
**Voglio** caricare, cachare e servire i dati di reskilling
**Per** includerli nel Knowledge Profile e nelle decisioni LLM

**Acceptance Criteria:**
- [ ] Schema Pydantic `ReskillingRecord` + `ReskillingStatus`
- [ ] CSV format guide documentato (`docs/reskilling_format_guide.md`)
- [ ] Loader CSV con validazione (pattern availability)
- [ ] Redis cache con TTL configurabile
- [ ] Service con get/get_bulk/filter
- [ ] Integrazione Celery task per refresh

**Story Points:** 5
**Priority:** P1 - High
**Status:** 🔜 Sprint 5
**Ref:** LLM-study.md §8

---

### US-009.3: KP Schema e Builder Base
**Come** sistema
**Voglio** un modello KnowledgeProfile assemblato dalle 4 sorgenti dati
**Per** fornire contesto ricco all'LLM per decisioni multi-scenario

**Acceptance Criteria:**
- [ ] Schema KnowledgeProfile (Pydantic v2)
- [ ] IC sub-state calculator
- [ ] KP Builder service (assembly da Qdrant + Redis availability + Redis reskilling + dictionary)
- [ ] KP Context serializer strutturato
- [ ] Test con dati di esempio

**Story Points:** 5
**Priority:** P1 - High
**Status:** 🔜 Sprint 5
**Ref:** LLM-study.md §3, §7, §9

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
**Status:** 🔜 Sprint 5

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
**Status:** 🔜 Sprint 5

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
**Status:** 🔜 Sprint 5

---

## Epic 6: Operations & Quality
> Monitoring, logging, manutenzione e qualità

### US-014: Test Coverage Improvement (Technical Debt)
**Come** sviluppatore
**Voglio** migliorare la coverage dei test
**Per** garantire qualità e regressione controllata

**Acceptance Criteria:**
- [ ] Coverage ≥ 80% su moduli core
- [ ] Integration test per pipeline
- [ ] Test per edge cases

**Story Points:** 5
**Priority:** P2 - Medium
**Status:** Open

---

### US-015: Dependency Cleanup & Linting Consolidation ✅
**Come** sviluppatore
**Voglio** ripulire le dipendenze e consolidare il linting
**Per** ridurre il debito tecnico e migliorare la DX

**Acceptance Criteria:**
- [x] Dipendenze non utilizzate rimosse
- [x] Ruff configurato come linter/formatter unico
- [x] CI aggiornata

**Story Points:** 3
**Priority:** P2 - Medium
**Status:** ✅ Completata

---

### US-017: Availability Task Monitoring API ✅
**Come** ops engineer
**Voglio** monitorare lo stato dei task di refresh disponibilità
**Per** verificare che la pipeline funzioni correttamente

**Acceptance Criteria:**
- [x] Endpoint GET /api/v1/availability/tasks
- [x] Stato aggregato via Celery inspect
- [x] Endpoint trigger e status

**Story Points:** 3
**Priority:** P2 - Medium
**Status:** ✅ Completata

---

## Sprint Planning MVP

### Sprint 1 (2 settimane) ✅
- US-001: Setup Repository ✅
- US-002: Setup Qdrant ✅
- US-003: Parser CV DOCX ✅

### Sprint 2 (2 settimane) ✅
- US-004: Skill Extraction ✅
- US-005: Embedding Pipeline ✅
- US-013: Celery Job Queue ✅

### Sprint 3 (2 settimane) ✅
- US-006: API Ricerca Skill ✅
- US-007: Filtro Disponibilità ✅
- US-015: Dependency Cleanup ✅

### Sprint 4 (2 settimane) — IN CORSO
- US-009: LLM Decision Engine ✅
- US-008: Match Job Description ⬅️ **prossimo step** (dipende da US-009 ✅)
- US-016: Orchestrazione Scraper ✅
- US-017: Availability Task Monitoring ✅

### Sprint 5 (2 settimane)
- US-009.1: Seniority Calculator (2 SP)
- US-009.2: Reskilling Infrastructure (5 SP)
- US-009.3: KP Schema e Builder Base (5 SP)
- US-010: Source Attribution (5 SP)

### Sprint 6 (2 settimane)
- US-011: Chat Interface
- US-012: Visualizzazione Profili

---

## Story Points Summary

| Priority | Stories | Total Points | Completati |
|----------|---------|--------------|-----------|
| P0 - Critical | 6 | 50 | 50 ✅ |
| P1 - High | 7 | 46 | 21 ✅ |
| P2 - Medium | 6 | 29 | 11 ✅ |
| P3 - Low | 0 | 0 | 0 |
| **Total** | **19** | **125** | **82 (66%)** |

**Velocity effettiva:** ~22 SP/sprint (Sprint 1-3 media)
**Sprint 4 rimanente:** US-008 (13 SP) — in corso
**Sprint 5 pianificato:** US-009.1 (2) + US-009.2 (5) + US-009.3 (5) + US-010 (5) = 17 SP
**MVP completabile in:** ~2 sprint rimanenti
