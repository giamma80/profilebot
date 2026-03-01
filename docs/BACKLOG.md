# Product Backlog - ProfileBot MVP

> **Ultimo aggiornamento:** 2 marzo 2026

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
**Status:** ✅ Completata (Sprint 4)

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

### US-009.1: Seniority Calculator ✅
**Come** sistema
**Voglio** calcolare il seniority_bucket in base a esperienze e skill
**Per** sbloccare il campo oggi hardcoded a "unknown" nel KP

**Acceptance Criteria:**
- [x] Euristica basata su years_experience + skill count + ruolo
- [x] Integrazione in EmbeddingPipeline (rimuovere hardcode "unknown")
- [x] Test con profili di diverse seniority
- [x] Payload Qdrant aggiornato con valore calcolato

**Story Points:** 2
**Priority:** P1 - High
**Status:** ✅ Completata (Sprint 6) — [#44](https://github.com/giamma80/profilebot/issues/44)
**Ref:** LLM-study.md §3.4, §12.1 gap #2

---

### US-009.2: Reskilling Infrastructure
**Come** sistema
**Voglio** caricare, cachare e servire i dati di reskilling
**Per** includerli nel Knowledge Profile e nelle decisioni LLM

**Acceptance Criteria:**
- [ ] Schema Pydantic `ReskillingRecord` + `ReskillingStatus`
- [ ] JSON row normalizer (mapping campi SharePoint raw → Pydantic)
- [ ] `ScraperClient.fetch_reskilling_row(res_id)` integrato
- [ ] Redis cache con TTL configurabile
- [ ] Service con get/get_bulk/filter
- [ ] Integrazione Celery task per refresh (REST → normalize → cache)

**Story Points:** 5
**Priority:** P1 - High
**Status:** 🔜 Sprint 6 — [#45](https://github.com/giamma80/profilebot/issues/45)
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
**Status:** 🔜 Sprint 6 — [#46](https://github.com/giamma80/profilebot/issues/46)
**Ref:** LLM-study.md §3, §7, §9

---

### US-009.4: Integrazione KP Context nella Pipeline di Matching ✅
**Come** sistema
**Voglio** che la pipeline di matching utilizzi KPBuilder + KPContextSerializer al posto del contesto flat attuale
**Per** fornire all'LLM un contesto ricco (availability, reskilling, IC sub-state, skill per domain) e ottenere ranking più accurati e motivazioni più complete

**Acceptance Criteria:**
- [x] Nuovo metodo `KPBuilder.build_from_search()` che costruisce il KP dal payload arricchito + availability/reskilling da Redis
- [x] `build_candidates_context_structured()` in `candidate_ranker.py` per ogni candidato top-K via `KPBuilder.build_from_search()`
- [x] Sostituire `build_candidates_context()` (deprecata, delegata a `build_candidates_context_flat()`)
- [x] Aggiornare `RANKING_SYSTEM_PROMPT` e `RANKING_USER_PROMPT` per il contesto strutturato
- [x] L'output LLM (`CandidateMatch`) include `strengths`, `gaps`, `explanation`
- [x] Fallback `search_only_rank()` invariato
- [x] Token budget: contesto per 7 candidati ≤ `llm_max_tokens * 0.6` (3 config progressive in `_KP_SERIALIZER_CONFIGS`)
- [x] Test unitari: mock KPBuilder + mock LLM (`test_renders_kp_blocks`, `test_fallbacks_to_flat_on_builder_error`)
- [x] Backward compatible: se KPBuilder fallisce per un candidato, fallback al formato flat
- [ ] Integration test e2e (JD → search → KP → LLM → CandidateMatch) — coperto parzialmente dai test con mock; vero e2e richiede Qdrant+Redis+LLM
- [ ] Note review non bloccanti: (1) reskilling merge contorto in `build_from_search`, (2) availability None forza fallback flat — TODO configurabilità futura

**Story Points:** 5
**Priority:** P1 - High
**Status:** ⏳ In Review (Sprint 7) — [#54](https://github.com/giamma80/profilebot/issues/54) — AC funzionali completati, restano note review non bloccanti
**Ref:** LLM-study.md §6.2 (Scenario Matching), §9 (Context Builder), §13 Fase 3
**Dipendenze:** US-009.2 ✅, US-009.3 ✅, US-009.5 ✅

**Note tecniche:**
- Punto di wiring: `candidate_ranker.py` → `build_candidates_context_structured()` con `KPContextSerializer`
- `KPBuilder.build_from_search(match, qdrant_payload, query_skills)` lavora con il payload arricchito (US-009.5)
- Graceful degradation: se payload non arricchito (CV pre-009.5), fallback flat per quel candidato
- `if profile.availability is None: raise ValueError(...)` → TODO: `Settings.kp_require_availability`

---

### US-009.5: Arricchimento Payload Qdrant per KP ✅
**Come** sistema
**Voglio** che il payload Qdrant `cv_skills` contenga i dati strutturati necessari al KPBuilder
**Per** consentire la costruzione del Knowledge Profile direttamente dal risultato di ricerca, senza dover re-parsare i CV

**Contesto:**
Oggi il payload `cv_skills` in Qdrant contiene solo: `cv_id`, `res_id`, `normalized_skills` (lista flat), `skill_domain`, `seniority_bucket`, `dictionary_version`. Mancano: `full_name`, `current_role`, `experiences`, `confidence/match_type` per skill, `unknown_skills`. Questa US arricchisce il payload durante l'embedding e triggera un re-embedding dei CV esistenti.

**Acceptance Criteria:**
- [x] Arricchire `pipeline.py → _build_skills_points()` con: `full_name`, `current_role`, `skill_details`, `unknown_skills`, `experiences_compact`, `years_experience_estimate`
- [x] Il campo `description_summary` è troncato a 200 caratteri per contenere il payload size
- [x] `_build_experience_points()` invariato (i chunk experience restano separati)
- [x] Test unitari: verificare che il payload generato contenga i nuovi campi
- [x] Test di regressione: i vecchi test della pipeline continuano a passare
- [x] Re-embedding dei CV esistenti eseguibile via `embed_all_task` (operazione idempotente). **Nota:** trigger manuale; automazione discovery demandata a TD-005 (#57)
- [x] Documentare il nuovo schema payload in docstring su `_build_skills_points()`

**Story Points:** 3
**Priority:** P1 - High
**Status:** ✅ Completata (Sprint 7) — [#56](https://github.com/giamma80/profilebot/issues/56)
**Ref:** LLM-study.md §5 (Hybrid Context), §9 (Context Builder)
**Dipendenze:** nessuna (infrastrutturale, tocca solo la pipeline di ingestion)

**Note tecniche:**
- Modifica confinata a `src/core/embedding/pipeline.py → _build_skills_points()`
- Costo storage Qdrant: pochi KB aggiuntivi per punto, trascurabile
- Il re-embedding è idempotente grazie ai point ID deterministici (`_generate_point_id`)
- Perché non Redis store separato: overengineering, Qdrant può ospitare i dati nel payload
- Perché non re-parsing al volo: lento, richiede accesso filesystem, fragile

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
**Status:** 🔜 Sprint 5 - UI — [#15](https://github.com/giamma80/profilebot/issues/15)

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
**Status:** 🔜 Sprint 5 - UI — [#16](https://github.com/giamma80/profilebot/issues/16)

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
**Status:** 🔜 Sprint 5 - UI — [#17](https://github.com/giamma80/profilebot/issues/17)

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

### TD-005: Automazione Embedding nel Workflow di Ingestion
**Come** sistema
**Voglio** che l'embedding dei CV venga eseguito automaticamente al termine del ciclo di scraping
**Per** eliminare la dipendenza da task manuali e garantire che Qdrant sia sempre allineato con i CV più recenti

**Contesto:**
Oggi il workflow `res_id_ingestion` (schedule `0 */4 * * *`) esegue 4 nodi: fetch res_id, fanout POST per produrre i CV lato scraper, export availability CSV, export reskilling CSV. Ma **nessuno scarica i CV** prodotti e **nessuno li indicizza** in Qdrant. L'embedding è triggerabile solo via API (`POST /api/v1/embeddings/trigger`) passando manualmente una lista `{cv_path, res_id}` che presuppone file su filesystem locale — approccio non coerente con l'architettura a servizi.

Il contratto scraper service prevede due step per i CV:
- `POST /inside/cv/{res_id}` → **produce** il file DOCX lato scraper (ritorna `{path}` locale al servizio)
- `GET /inside/cv/{res_id}` → **scarica** il file come bytes binari (`format: binary`)

Oggi ProfileBot esegue solo il POST (via `ScraperClient.refresh_inside_cv`) senza mai fare la GET. Inoltre:
- `ScraperClient._request()` fa sempre `.json()` → non gestisce risposte binarie
- `DocxParser.parse()` accetta solo `Path` → non supporta `bytes`/`BytesIO`
- `_extract_res_id()` estrae il res_id dal filename → impossibile con stream in memoria
- `_embed_cv()` e `embed_all_task` lavorano solo con file path su filesystem

**Acceptance Criteria:**

_1. ScraperClient: download CV binario_
- [x] Nuovo metodo `ScraperClient.download_inside_cv(res_id: int) -> bytes` che fa `GET /inside/cv/{res_id}` e ritorna i bytes grezzi del DOCX
- [x] `_request()` o nuovo metodo `_request_binary()` che gestisce `Content-Type: application/vnd.openxmlformats-...` senza `.json()`
- [x] Test unitario: mock httpx → verifica che download_inside_cv ritorna bytes e gestisce 404/500

_2. DocxParser: parsing da bytes in memoria_
- [x] Nuovo metodo `DocxParser.parse_bytes(data: bytes, res_id: int, filename: str | None = None) -> ParsedCV` che parsa da `BytesIO` senza accesso al filesystem
- [x] Il `res_id` viene passato come parametro (non estratto dal filename); `filename` è opzionale per metadata
- [x] `python-docx` supporta nativamente `BytesIO` come input a `Document()`
- [x] Funzione helper `parse_docx_bytes(data: bytes, res_id: int) -> ParsedCV` (analog a `parse_docx`)
- [x] Test unitario: bytes di un DOCX valido → `ParsedCV` con res_id corretto; bytes corrotti → `CVParseError`

_3. Embedding task: embed da scraper service_
- [x] Nuovo task `embed_from_scraper_task` in `src/services/embedding/tasks.py` che: (a) legge lista res_id da Redis (`profilebot:scraper:inside:res_ids`), (b) per ogni res_id chiama `ScraperClient.download_inside_cv(res_id)` → `parse_docx_bytes()` → `SkillExtractor.extract()` → `EmbeddingPipeline.process_cv()`, (c) ritorna summary con conteggi
- [x] Resilienza: se download o parsing fallisce per un res_id, log + skip, prosegui con i successivi
- [x] Progress tracking via `self.update_state(state="PROGRESS", meta={...})` come in `embed_all_task`
- [x] Idempotenza garantita da `_generate_point_id()` deterministico (hash cv_id + section_type) → upsert sovrascrive

_4. Integrazione nel Workflow YAML_
- [x] Aggiungere nodo `embed_all` in `config/workflows/res_id_workflow.yaml` con `depends_on: [inside_fanout]`
- [x] Il nodo usa `task: src.services.embedding.tasks.embed_from_scraper_task`
- [x] Verificare che il runner DAG produca la canvas corretta: i nodi export restano paralleli, `embed_all` dipende da `inside_fanout`

_5. Test_
- [x] Test unitario `embed_from_scraper_task`: mock ScraperClient + mock EmbeddingPipeline, verificare che il flusso download → parse_bytes → extract → process_cv funzioni per N res_id
- [x] Test resilienza: 1 res_id su 3 fallisce download → task completa con 2 successi + 1 errore loggato
- [x] Test idempotenza: mock che verifica che `_generate_point_id()` produce ID stabili → upsert non duplica
- [x] Test integrazione workflow: caricare il YAML aggiornato, verificare che il canvas Celery includa il nodo `embed_all` dopo `inside_fanout`

_6. Target Make (opzionale)_
- [x] Aggiungere `make embed-all` al Makefile che invoca `embed_from_scraper_task` via Celery per trigger manuale one-shot

**Story Points:** 5
**Priority:** P1 - High
**Status:** ✅ Completata (Sprint 8) — [#57](https://github.com/giamma80/profilebot/issues/57)
**Ref:** Analisi architetturale 01/03/2026, OpenAPI scraper-service (`docs/scraper-service/scraper-service-openapi.yaml`)
**Dipendenze:** US-005 ✅, US-016 ✅, US-009.5 ✅

**Note tecniche:**
- Il workflow engine (`src/core/workflows/`) supporta nativamente il nuovo nodo: `WorkflowNode` con `depends_on`, il runner converte in Celery `chain`/`group`
- `python-docx` accetta `BytesIO` nativamente: `Document(BytesIO(data))` — zero dipendenze aggiuntive
- L'embedding pipeline usa `_generate_point_id()` deterministico (hash cv_id + section_type) → upsert idempotente, nessun duplicato
- Il payload è già arricchito (US-009.5): `full_name`, `current_role`, `skill_details`, `experiences_compact`, `unknown_skills`, `years_experience_estimate`
- Schedule attuale `0 */4 * * *` (ogni 4 ore) è adeguato anche per l'embedding: il costo aggiuntivo è ~$0.01/CV per embedding OpenAI
- Story points aumentati da 3 a 5: il refactor del parser e del client aggiunge complessità rispetto alla versione filesystem-only
- Non serve `cv_storage_dir` in Settings: i CV vengono scaricati on the fly dal scraper service e parsati in memoria

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

### Sprint 4 — Matching (2 settimane) ✅
- US-009: LLM Decision Engine ✅
- US-008: Match Job Description ✅
- US-016: Orchestrazione Scraper ✅
- US-017: Availability Task Monitoring ✅

### Sprint 5 — UI (2 settimane)
- US-010: Source Attribution (5 SP) — [#15](https://github.com/giamma80/profilebot/issues/15)
- US-011: Chat Interface (8 SP) — [#16](https://github.com/giamma80/profilebot/issues/16)
- US-012: Visualizzazione Profili (5 SP) — [#17](https://github.com/giamma80/profilebot/issues/17)

### Sprint 6 — KP Foundation (2 settimane) ⬅️ IN CORSO
- US-009.1: Seniority Calculator (2 SP) ✅ — [#44](https://github.com/giamma80/profilebot/issues/44)
- US-009.2: Reskilling Infrastructure (5 SP) — [#45](https://github.com/giamma80/profilebot/issues/45)
- US-009.3: KP Schema e Builder Base (5 SP) — [#46](https://github.com/giamma80/profilebot/issues/46)
- TD-001: Connector Contract (3 SP) — [#47](https://github.com/giamma80/profilebot/issues/47)
- TD-004: Resilience Base (3 SP) — [#48](https://github.com/giamma80/profilebot/issues/48)

### Sprint 7 — Scenario Matching (2 settimane) ⏳ In Review
- US-009.5: Arricchimento Payload Qdrant per KP (3 SP) ✅ — [#56](https://github.com/giamma80/profilebot/issues/56)
- US-009.4: Integrazione KP Context nella Pipeline di Matching (5 SP) ⏳ — [#54](https://github.com/giamma80/profilebot/issues/54) — restano note review non bloccanti

### Sprint 8 — Automazione & Stabilizzazione (2 settimane) ✅
- TD-005: Automazione Embedding nel Workflow (5 SP) ✅ — [#57](https://github.com/giamma80/profilebot/issues/57)

---

## Story Points Summary

| Priority | Stories | Total Points | Completati |
|----------|---------|--------------|-----------|
| P0 - Critical | 6 | 50 | 50 ✅ |
| P1 - High | 10 | 59 | 44 ✅ + 5 ⏳ |
| P2 - Medium | 6 | 29 | 11 ✅ |
| P3 - Low | 0 | 0 | 0 |
| **Total** | **22** | **138** | **105 ✅ + 5 ⏳ (80%)** |

**Velocity effettiva:** ~22 SP/sprint (Sprint 1-4 media)
**Sprint 4 completato:** US-008 (13 SP) + US-009 (8 SP) + US-016 (5 SP) + US-017 (3 SP)
**Sprint 6 in corso:** US-009.1 ✅ (2) + US-009.2 (5) + US-009.3 (5) + TD-001 (3) + TD-004 (3) = 18 SP (2 completati)
**Sprint 7 in review:** US-009.5 ✅ (3 SP) + US-009.4 ⏳ (5 SP) = 8 SP — US-009.5 completata, US-009.4 restano note review non bloccanti
**Sprint 8 completato:** TD-005 ✅ (5 SP)
**MVP completabile in:** ~1-2 sprint rimanenti
