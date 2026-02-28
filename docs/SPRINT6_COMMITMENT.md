# Sprint 6 Commitment — KP Foundation

> **Sprint:** 6
> **Milestone GitHub:** Sprint 6 - KP Foundation
> **Durata:** 2 settimane (27 feb – 13 mar 2026)
> **Velocity target:** 18 SP (media storica: ~22 SP/sprint)
> **SP completati al 28/02:** 2/18 (US-009.1 chiusa)
> **Tema:** Costruire le fondamenta del Knowledge Profile per abilitare decisioni LLM multi-scenario

---

## Sprint Goal

**Sbloccare il Knowledge Profile (KP) come modello dati unificato per l'LLM**, implementando le 3 sorgenti dati mancanti (seniority calcolata, reskilling via REST API, KP assembly) e iniziando il consolidamento dell'infrastruttura di ingestion (connector contract, resilience).

Al termine dello sprint, il sistema sarà in grado di assemblare un KP completo per qualsiasi profilo e fornirlo come contesto strutturato all'LLM.

---

## Stato Issue

| # | Issue | GitHub | SP | Stato | Dipendenze | Branch |
|---|-------|--------|----|-------|------------|--------|
| 1 | **US-009.1** Seniority Calculator | [#44](https://github.com/giamma80/profilebot/issues/44) | 2 | ✅ Done | — | `feature/US-009.1-seniority` |
| 2 | **US-009.2** Reskilling Infrastructure | [#45](https://github.com/giamma80/profilebot/issues/45) | 5 | 🔵 To Do | — | `feature/US-009.2-reskilling` |
| 3 | **US-009.3** KP Schema e Builder Base | [#46](https://github.com/giamma80/profilebot/issues/46) | 5 | 🔵 To Do | US-009.1 ✅, US-009.2 | `feature/US-009.3-kp-builder` |
| 4 | **TD-001** Connector Contract (starter) | [#47](https://github.com/giamma80/profilebot/issues/47) | 3 | 🔵 To Do | — | `feature/TD-001-connector-contract` |
| 5 | **TD-004** Resilience Base (metrics + CB) | [#48](https://github.com/giamma80/profilebot/issues/48) | 3 | 🔵 To Do | — | `feature/TD-004-resilience-base` |
| | **TOTALE** | | **18** | **2 done** | | |

---

## Sequenza di Lavoro Aggiornata

US-009.1 è completata e mergiata su `main` (giorno 1-2). Il piano di lavoro per i giorni rimanenti:

```
Week 1 — giorni rimanenti (3-5)
├── TD-001 Connector Contract ─────────── [giorno 3-4] (indipendente)
├── TD-004 Resilience Base ────────────── [giorno 3-4] (parallelizzabile con TD-001)
└── US-009.2 Reskilling Infrastructure ── [giorno 3-5] (start)

Week 2 (giorni 6-10)
├── US-009.2 completamento + test ─────── [giorno 6-7]
├── US-009.3 KP Schema e Builder ──────── [giorno 7-9] (dopo US-009.2)
└── Review + fix + merge ──────────────── [giorno 9-10]
```

### Critical Path

```
US-009.1 (seniority) ✅ ──┐
                           ├──→ US-009.3 (KP Builder) ──→ SPRINT GOAL ✅
US-009.2 (reskilling) ────┘

TD-001 e TD-004 sono indipendenti e parallelizzabili in Week 1.
```

> **Nota:** La dipendenza bloccante rimasta è US-009.2 → US-009.3. Se US-009.2 ritarda, US-009.3 può essere sviluppata con mock tramite Protocol e integrata al merge.

---

## Dettaglio per Issue

### ✅ US-009.1 — Seniority Calculator (2 SP) — COMPLETATA

**Obiettivo:** Calcolare `seniority_bucket` deterministico da esperienze e skill, eliminando l'hardcode `"unknown"`.

**Risultato:**

- `src/core/seniority/calculator.py` — euristica basata su years_exp + skill_count + role_keywords
- Integrazione in `EmbeddingPipeline` completata (hardcode rimosso)
- Payload Qdrant aggiornato con `seniority_bucket` calcolato
- Test cases coperti: junior, mid, senior, lead, unknown
- PR mergiata su `main`, issue #44 chiusa

---

### US-009.2 — Reskilling Infrastructure (5 SP)

**Obiettivo:** Layer completo per consumare dati di reskilling via REST API dallo scraper service, normalizzarli, cacharli in Redis e servirli al KP Builder.

**Pattern architetturale:** I dati di reskilling provengono dall'endpoint REST dello scraper service `GET /reskilling/csv/{res_id}`, che restituisce un JSON `{res_id, row}` con campi SharePoint dinamici (`additionalProperties: true`). Il contratto è definito in `docs/scraper-service/scraper-service-openapi.yaml`.

**Deliverable:**

- `src/services/reskilling/schemas.py` — `ReskillingRecord(BaseModel)` + `ReskillingStatus(StrEnum)`
- `src/services/reskilling/normalizer.py` — mapping campi SharePoint raw → Pydantic, con log warning su campi sconosciuti e fallback safe
- `src/services/scraper/client.py` — nuovo metodo `fetch_reskilling_row(res_id: int) → dict` che chiama `GET /reskilling/csv/{res_id}`
- `src/services/reskilling/cache.py` — `ReskillingCache` con Redis, TTL configurabile via `RESKILLING_CACHE_TTL`
- `src/services/reskilling/service.py` — `ReskillingService` con get/get_bulk/filter
- `src/services/scraper/tasks.py` — Celery task `reskilling_refresh_task` (REST → normalize → cache)
- `src/core/config.py` — nuovi settings: `reskilling_cache_ttl`, `reskilling_refresh_schedule`
- Test: ≥ 8 test cases (normalizer, cache, service, task con mock)

**Acceptance Criteria:**

- [ ] Schema Pydantic `ReskillingRecord` + `ReskillingStatus`
- [ ] JSON row normalizer (mapping campi SharePoint raw → Pydantic)
- [ ] `ScraperClient.fetch_reskilling_row(res_id)` integrato
- [ ] Redis cache con TTL configurabile
- [ ] Service con get/get_bulk/filter
- [ ] Celery task reskilling_refresh_task (REST → normalize → cache)
- [ ] 80%+ coverage sui nuovi moduli

**Rischi:** Medio. Il mapping dei campi SharePoint dinamici potrebbe richiedere aggiornamento se il tracciato sorgente cambia. Il campo `row` nell'API ha `additionalProperties: true`, il che significa che nuovi campi possono apparire senza preavviso.

**Mitigazione:** Normalizer con log warning su campi sconosciuti + fallback safe (`None` per campi opzionali). Il normalizer è l'unico punto di accoppiamento con la struttura dati sorgente.

---

### US-009.3 — KP Schema e Builder Base (5 SP)

**Obiettivo:** Modello `KnowledgeProfile` unificato che assembla dati da 4 sorgenti (Qdrant, availability, reskilling, dictionary).

**Deliverable:**

- `src/core/knowledge_profile/schemas.py` — Schema `KnowledgeProfile` con sezioni: identity, skills, seniority, experiences, availability, ic_sub_state, reskilling
- `src/core/knowledge_profile/ic_sub_state.py` — `ICSubStateCalculator` (not_ic / ic_available / ic_in_reskilling / ic_in_transition)
- `src/core/knowledge_profile/builder.py` — `KPBuilder` service (assembly dalle 4 sorgenti)
- `src/core/knowledge_profile/serializer.py` — `KPContextSerializer` (output strutturato per prompt LLM)
- Token budget estimator
- Test: ≥ 8 test cases (builder con mock, serializer, IC sub-state)

**Rischi:** Medio-alto. Dipende da US-009.1 (✅ completata) e US-009.2. Se US-009.2 ritarda, il KP Builder può essere sviluppato con mock/stub e integrato dopo.

**Mitigazione:** Definire le interfacce `get_seniority()` e `get_reskilling()` come Protocol, sviluppare Builder con mock, integrare reale in fase di merge.

---

### TD-001 Starter — Connector Contract (3 SP)

**Obiettivo:** Definire il Protocol `IngestionSource` e migrare il DOCX parser come primo adapter.

**Deliverable:**

- Protocol `IngestionSource` (fetch/validate/normalize)
- Schema `NormalizedDocument` + `IngestionMetadata`
- Error hierarchy (`IngestionError` → `FetchError`, `ValidationError`, `NormalizationError`)
- DOCX adapter (backward-compatible, wrapper pattern)

**Rischi:** Basso. Adapter pattern non rompe nulla. Scope limitato al contratto + 1 migrazione.

**Ref:** `docs/technical_debt.md` §TD-001

---

### TD-004 — Resilience Base (3 SP)

**Obiettivo:** Metriche ingestion strutturate + circuit breaker base.

**Deliverable:**

- `IngestionMetrics` con contatori per source_type (Redis-backed)
- Decoratore `@track_ingestion` per task Celery
- `CircuitBreaker` state machine (closed → open → half_open)
- Endpoint GET `/api/v1/metrics/ingestion`

**Rischi:** Basso. Pattern noti, scope contenuto. Il circuit breaker è una state machine semplice.

**Ref:** `docs/technical_debt.md` §TD-004

---

## Definition of Done (Sprint-level)

- [ ] Tutte le issue hanno PR approvata e mergiata su `main`
- [ ] Test passano su CI (ruff + pytest)
- [ ] Coverage ≥ 80% sui nuovi moduli
- [x] Nessun hardcode `"unknown"` residuo per seniority (✅ US-009.1)
- [ ] Reskilling layer consuma dati esclusivamente via REST API dello scraper service
- [ ] KP Builder assembla profilo completo con dati reali o mock
- [ ] Documentazione aggiornata (BACKLOG.md, OpenAPI ref dello scraper service)

---

## Metriche di Successo

| Metrica | Target | Attuale |
|---------|--------|---------|
| SP completati | ≥ 15/18 (83%) | 2/18 (11%) |
| Issue chiuse | ≥ 4/5 | 1/5 |
| Test aggiunti | ≥ 25 nuovi test | — |
| Coverage nuovi moduli | ≥ 80% | — |

---

## Dipendenze Esterne

Nessuna dipendenza esterna bloccante. Tutti i dati necessari sono accessibili tramite lo scraper service REST API:

- **Reskilling:** `GET /reskilling/csv/{res_id}` → JSON `{res_id, row}`
- **Availability:** `GET /availability/csv` → JSON array
- **CV DOCX:** `GET /inside/resource/{res_id}` → binary

Il contratto API completo è documentato in `docs/scraper-service/scraper-service-openapi.yaml`.

---

## Nota Architetturale — Pattern REST

A partire da questo sprint, tutti i dati esterni (reskilling, availability) vengono consumati esclusivamente tramite le REST API dello scraper service. Non esistono CSV locali da parsare: lo scraper service espone endpoint JSON che il backend ProfileBot consuma tramite `ScraperClient` (httpx).

Questo pattern semplifica l'architettura:

- **Nessun file system condiviso** — niente CSV su disco, niente path configurabili
- **Contratto tipizzato** — lo schema OpenAPI dello scraper è la source of truth
- **Unico punto di accoppiamento** — il normalizer (per reskilling) o il loader (per availability) gestisce il mapping API → Pydantic
- **Cache Redis** — i dati normalizzati vengono cachati con TTL configurabile

---

## Cosa NON è nello scope

- US-010 (Source Attribution) — spostata a Sprint 5 - UI (milestone esistente)
- US-008 completamento AC mancanti — merge in corso su Sprint 4
- Prefect/Dagster setup (TD-005 Fase 2) — future sprint
- UI (US-011, US-012) — Sprint 5 - UI
- Migrazione availability da CSV a REST — fuori scope, funziona già

---

## Post-Sprint: cosa abilita

Con il KP Foundation completato, gli sprint successivi potranno:

1. **Multi-scenario prompting** — matching, gap analysis, reskilling suggestion usano lo stesso KP
2. **Source Attribution (US-010)** — il KP traccia da dove viene ogni dato
3. **Chat Interface (US-011)** — il KP è il contesto per la conversazione
4. **Reskilling Suggestion scenario** — il prompt può ragionare su corsi in corso e gap colmabili

---

*Ultimo aggiornamento: 28 febbraio 2026*
