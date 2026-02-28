# Sprint 6 — Guida per gli Sviluppatori

> **Destinatari:** Team di sviluppo ProfileBot
> **Sprint:** 6 — KP Foundation (27 feb – 13 mar 2026)
> **Ultimo aggiornamento:** 28 febbraio 2026

---

## 1. Come Orientarsi nella Documentazione

La documentazione del progetto è organizzata in `docs/`. Ecco l'ordine di lettura consigliato prima di iniziare a lavorare sulle issue di questo sprint.

### Lettura obbligatoria (per tutti)

1. **`docs/SPRINT6_COMMITMENT.md`** — Il commitment dello sprint. Contiene lo sprint goal, la tabella delle issue con stati e dipendenze, la sequenza di lavoro consigliata, il dettaglio per ogni issue (deliverable, AC, rischi), la Definition of Done e le metriche di successo. **Partite sempre da qui.**

2. **`docs/BACKLOG.md`** — Il backlog completo con tutte le User Story. Cercate la vostra issue (US-009.2, US-009.3, TD-001, TD-004) per leggere il contesto della US, gli Acceptance Criteria e le dipendenze.

3. **La vostra Issue su GitHub** — Ogni issue (#45, #46, #47, #48) ha un body strutturato con AC, architettura, file coinvolti e DoD specifica. Il body delle issue è allineato con i documenti locali.

### Lettura consigliata (per issue specifiche)

| Se lavori su... | Leggi anche... |
|-----------------|---------------|
| **US-009.2** Reskilling | `docs/LLM-study.md` §8 (Reskilling Infrastructure), `docs/scraper-service/scraper-service-openapi.yaml` (contratto API), `src/services/availability/` (pattern di riferimento) |
| **US-009.3** KP Builder | `docs/LLM-study.md` §3 (Knowledge Profile model), §4 (sorgenti dati), §7 (IC sotto-stati), §9 (Context Builder) |
| **TD-001** Connector | `docs/technical_debt.md` §TD-001, `docs/LLM-study.md` §12 (gap analysis) |
| **TD-004** Resilience | `docs/technical_debt.md` §TD-004 |

### Riferimenti architetturali

Per il quadro complessivo dell'architettura e le scelte di design, i documenti chiave sono `docs/LLM-study.md` (lo studio completo sul Knowledge Profile e il multi-scenario prompting), `docs/analisi_preliminare.md` (le decisioni fondanti del progetto) e `docs/appendice_tecnica_indexing.md` (la pipeline di indicizzazione).

---

## 2. Pattern Architetturale — ATTENZIONE

### I dati esterni arrivano via REST API, NON via CSV

Questo è il punto più importante da capire prima di scrivere codice. A partire da questo sprint, **tutti i dati esterni (reskilling, availability) vengono consumati esclusivamente tramite le REST API dello scraper service**. Non esistono CSV locali da parsare.

Lo scraper service è un servizio separato che fa scraping delle sorgenti aziendali (SharePoint, Inside) e espone i dati tramite endpoint REST. Il contratto è in `docs/scraper-service/scraper-service-openapi.yaml`.

In pratica:

- **NON** cercate file CSV su disco
- **NON** scrivete loader/parser CSV per reskilling
- **NON** aggiungete `csv_path` ai settings
- **SÌ** usate `ScraperClient` (httpx) per chiamare l'API REST
- **SÌ** normalizzate il JSON ricevuto in Pydantic model

### Il flusso per i dati reskilling

```
Scraper Service                         ProfileBot
─────────────────                       ──────────────────────────────
GET /reskilling/csv/{res_id}    →       ScraperClient.fetch_reskilling_row()
        │                                       │
        ▼                                       ▼
JSON {res_id, row}              →       normalizer.py (JSON → ReskillingRecord)
                                                │
                                                ▼
                                        ReskillingCache (Redis, TTL)
                                                │
                                                ▼
                                        ReskillingService (get / get_bulk / filter)
                                                │
                                                ▼
                                        KP Builder (US-009.3)
```

### Perché l'endpoint si chiama `/reskilling/csv/{res_id}`?

Il path contiene "csv" perché lo scraper service internamente legge da un CSV SharePoint. Ma l'endpoint REST restituisce **JSON**, non CSV. Non fatevi ingannare dal nome dell'URL: il nostro codice non tocca mai file CSV.

---

## 3. Come Leggere le Issue su GitHub

Ogni issue dello Sprint 6 ha una struttura standard. Ecco come interpretarla.

### Struttura del body

Le issue contengono queste sezioni:

- **Obiettivo** — Cosa deve essere ottenuto, in una riga
- **Architettura / Pattern** — Come implementarlo (diagrammi, flussi dati)
- **File coinvolti** — Lista esatta dei file da creare o modificare
- **Acceptance Criteria** — Checklist con le checkbox. Ogni AC è una condizione che DEVE essere vera per chiudere l'issue
- **Settings** — Eventuali nuove variabili di configurazione
- **DoD** — Definition of Done specifica per l'issue (test, coverage, ruff, docs)
- **Ref** — Riferimenti a documenti di design

### Convenzione branch

Ogni issue ha un branch assegnato nella tabella del commitment:

- `feature/US-009.2-reskilling`
- `feature/US-009.3-kp-builder`
- `feature/TD-001-connector-contract`
- `feature/TD-004-resilience-base`

Create il branch da `main` aggiornato. La PR va verso `main`.

---

## 4. Indicazioni per Issue

### US-009.2 — Reskilling Infrastructure (5 SP)

**Chi lavora su questa issue** deve prima leggere `docs/scraper-service/scraper-service-openapi.yaml` (sezione `/reskilling/csv/{res_id}`) e studiare il modulo `src/services/availability/` come pattern di riferimento.

**Cosa fare, in ordine:**

1. **`src/services/reskilling/schemas.py`** — Definire `ReskillingStatus(StrEnum)` e `ReskillingRecord(BaseModel)` con i campi normalizzati. Usate `model_config = {"extra": "forbid"}` come in `ProfileAvailability`. I campi da mappare li trovate in `docs/LLM-study.md` §8.3.

2. **`src/services/reskilling/normalizer.py`** — Questo è il componente nuovo rispetto al pattern availability (che usa un loader CSV). Il normalizer prende il dict `row` dalla risposta JSON dell'API e lo trasforma in `ReskillingRecord`. I nomi dei campi SharePoint sono cose come `"Risorsa:Consultant ID"`, `"Stato"`, ecc. Il normalizer deve loggare un warning se trova campi sconosciuti e usare `None` come fallback per campi opzionali mancanti.

3. **`src/services/scraper/client.py`** — Aggiungere `fetch_reskilling_row(self, res_id: int) -> dict` che fa `self.get(f"/reskilling/csv/{res_id}")`. Guardate i metodi esistenti (`export_availability_csv`, ecc.) come riferimento per lo stile.

4. **`src/services/reskilling/cache.py`** — Copiate il pattern da `src/services/availability/cache.py`, cambiando `ProfileAvailability` → `ReskillingRecord`, key prefix `profilebot:reskilling`, TTL da `settings.reskilling_cache_ttl`.

5. **`src/services/reskilling/service.py`** — `ReskillingService` con metodi `get(res_id)`, `get_bulk(res_ids)`, `filter(status)`. Il service legge dalla cache; se miss, chiama client → normalizer → cache → return.

6. **`src/services/scraper/tasks.py`** — Nuovo task Celery `reskilling_refresh_task` che per ogni `res_id` noto chiama `fetch_reskilling_row` → normalizer → cache. Guardate `scraper_reskilling_csv_refresh_task` già esistente come punto di partenza (quel task fa solo il trigger dell'export, il nuovo task fa il fetch + normalize + cache).

7. **`src/core/config.py`** — Aggiungere `reskilling_cache_ttl: int = 3600` e `reskilling_refresh_schedule: str = "*/30 * * * *"` nella classe `Settings`.

**Cosa NON fare:**

- Non creare un `loader.py` — il loader è un pattern CSV, qui usiamo un normalizer JSON
- Non aggiungere `reskilling_csv_path` ai settings — non c'è nessun CSV locale
- Non modificare i file dell'availability service — sono corretti così

**Test:** Almeno 8 test case. Testate il normalizer con input valido, campi mancanti, campi extra (warning), e date in formati diversi. Testate cache e service con mock Redis. Testate il task con mock ScraperClient.

---

### US-009.3 — KP Schema e Builder Base (5 SP)

**Dipendenze:** US-009.1 è completata (potete usare `src/core/seniority/calculator.py`). US-009.2 deve essere completata o almeno avere le interfacce definite (schemas + service stub).

**Se US-009.2 non è ancora pronta:** Definite un Protocol `ReskillingProvider` con il metodo `get(res_id) -> ReskillingRecord | None` e sviluppate il Builder con un mock. Al merge di US-009.2 collegherete il `ReskillingService` reale.

**Cosa fare, in ordine:**

1. **`src/core/knowledge_profile/schemas.py`** — Schema `KnowledgeProfile` che aggrega identity, skills, seniority, experiences, availability, reskilling, ic_sub_state. Leggete `docs/LLM-study.md` §3.2 per la struttura proposta.

2. **`src/core/knowledge_profile/ic_sub_state.py`** — `ICSubStateCalculator` che calcola lo stato IC (not_ic, ic_available, ic_in_reskilling, ic_in_transition) a partire da availability + reskilling. Logica in `docs/LLM-study.md` §7.

3. **`src/core/knowledge_profile/builder.py`** — `KPBuilder` che assembla il KP dalle 4 sorgenti: Qdrant (via EmbeddingPipeline o query), AvailabilityService, ReskillingService, SkillDictionary. Ogni sorgente è opzionale: se una fallisce, il KP si costruisce comunque con i dati disponibili (graceful degradation).

4. **`src/core/knowledge_profile/serializer.py`** — `KPContextSerializer` che converte il KP in testo strutturato per il prompt LLM. Template in `docs/LLM-study.md` §9.2.

5. **Token budget estimator** — Funzione che stima i token necessari per serializzare un KP (approssimazione: `len(text) / 4`). Serve per decidere se attivare il livello 2 (chunk retrieval) o se il KP strutturato basta.

---

### TD-001 — Connector Contract Starter (3 SP)

**Questa issue è indipendente** e può procedere in parallelo con tutto il resto.

**Cosa fare:**

1. Definire il Protocol `IngestionSource` con i metodi `fetch()`, `validate()`, `normalize()` — è il contratto che tutte le future sorgenti dati dovranno implementare
2. Creare gli schema `NormalizedDocument` e `IngestionMetadata`
3. Definire la gerarchia errori: `IngestionError` → `FetchError`, `ValidationError`, `NormalizationError`
4. Migrare il DOCX parser esistente come primo adapter che implementa `IngestionSource` (backward-compatible, wrapper pattern)

**Leggete** `docs/technical_debt.md` §TD-001 per il rationale. L'obiettivo è standardizzare l'interfaccia di ingestion per poter aggiungere nuovi adapter (PDF, Excel, ecc.) in futuro senza toccare la pipeline core.

---

### TD-004 — Resilience Base (3 SP)

**Anche questa issue è indipendente** e parallelizzabile.

**Cosa fare:**

1. `IngestionMetrics` con contatori per `source_type`, backed by Redis
2. Decoratore `@track_ingestion` per task Celery (cattura successi, fallimenti, durata)
3. `CircuitBreaker` — state machine con 3 stati: closed (normale), open (source down, skip per N secondi), half_open (test 1 richiesta). Pattern standard.
4. Endpoint `GET /api/v1/metrics/ingestion` che espone i contatori

**Leggete** `docs/technical_debt.md` §TD-004.

---

## 5. Convenzioni di Codice

### Stile e linting

Il progetto usa **ruff** come linter e formatter. Prima di committare:

```bash
ruff check src/ tests/ --fix
ruff format src/ tests/
```

La CI fallirà se ruff trova errori.

### Pattern comuni nel codebase

- **Pydantic v2** per tutti gli schema: `BaseModel`, `model_config = {"extra": "forbid"}`, `Field(...)` con constraints
- **StrEnum** per enumerazioni (non `Enum` plain)
- **`from __future__ import annotations`** in testa a ogni file
- **Type hints** su tutte le firme pubbliche
- **`get_settings()`** da `src.core.config` per accedere ai settings (singleton, lru_cache)
- **Redis via `redis-py`**: `redis.from_url(settings.redis_url, decode_responses=True)`
- **Serializzazione cache**: `model_dump_json()` per scrivere, `Model.model_validate_json(raw)` per leggere
- **Celery tasks**: decoratore `@celery_app.task(bind=True, ...)`, retry con `self.retry(exc=exc, countdown=...)`
- **ScraperClient**: context manager con `httpx.Client`, usare `self.get(path)` / `self.post(path)`

### Struttura directory per un nuovo service

Se create `src/services/reskilling/`, la struttura attesa è:

```
src/services/reskilling/
├── __init__.py
├── schemas.py        # Pydantic models
├── normalizer.py     # JSON → Pydantic mapping
├── cache.py          # Redis cache layer
└── service.py        # Business logic
```

I test vanno in `tests/services/reskilling/` con la stessa struttura mirror.

---

## 6. Workflow Git

1. **Branching:** Create il branch dalla colonna "Branch" del commitment (`feature/US-009.2-reskilling`, ecc.) da `main` aggiornato
2. **Commit:** Commit atomici, messaggi in inglese, prefisso con l'issue: `[US-009.2] Add ReskillingRecord schema and normalizer`
3. **PR:** Titolo = `[US-009.X] Descrizione breve`. Body con checklist degli AC
4. **Review:** Almeno 1 approval prima del merge
5. **Merge:** Squash merge verso `main`

---

## 7. Checklist Pre-PR

Prima di aprire la PR, verificate:

- [ ] `ruff check` e `ruff format` passano senza errori
- [ ] `pytest` passa (tutti i test, non solo i vostri)
- [ ] Coverage ≥ 80% sui moduli nuovi
- [ ] Tutti gli AC dell'issue sono soddisfatti (controllate le checkbox nel body dell'issue)
- [ ] Nessun hardcode di URL, path, credenziali
- [ ] Settings nuovi hanno valori di default ragionevoli
- [ ] Docstring su classi e metodi pubblici

---

## 8. Domande Frequenti

**D: Dove trovo il contratto dell'API reskilling?**
R: `docs/scraper-service/scraper-service-openapi.yaml`, sezione `/reskilling/csv/{res_id}`. Lo schema di risposta è `RowResponse` con `res_id: string` e `row: object` (additionalProperties).

**D: Come faccio a sapere quali campi ha il `row` di reskilling?**
R: Il campo `row` ha `additionalProperties: true`, cioè i campi sono dinamici e dipendono da SharePoint. Un esempio è nell'OpenAPI: `"Risorsa:Consultant ID": "210513"`, `"Risorsa": "Donnemma, Debora"`. Il normalizer deve gestire sia i campi noti che quelli ignoti (log warning + skip).

**D: Posso copiare il loader dell'availability per reskilling?**
R: No, il loader availability è un parser CSV. Per reskilling non c'è nessun CSV locale da parsare. Create un **normalizer** che prende un dict JSON e restituisce un `ReskillingRecord`. Potete però copiare il pattern del **cache** (`availability/cache.py`) quasi identico.

**D: US-009.3 dipende da US-009.2. Come faccio se non è pronta?**
R: Definite un Protocol con la firma dei metodi che vi servono (`get(res_id) -> ReskillingRecord | None`) e usate un mock/stub. Quando US-009.2 è mergiata, sostituite il mock con `ReskillingService`.

**D: Dove aggiorno la documentazione quando ho finito?**
R: Spuntate le checkbox dell'AC nella vostra issue GitHub e aggiornate `docs/BACKLOG.md` marcando la vostra US come completata.

---

*Per qualsiasi dubbio architetturale non coperto da questa guida, fate riferimento a `docs/LLM-study.md` che è il documento di design più completo del progetto.*
