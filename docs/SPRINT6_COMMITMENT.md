# Sprint 6 Commitment — KP Foundation

> **Sprint:** 6
> **Milestone GitHub:** Sprint 6 - KP Foundation
> **Durata:** 2 settimane (27 feb – 13 mar 2026)
> **Velocity target:** 18 SP (media storica: ~22 SP/sprint)
> **SP completati al 01/03:** 7/18 (US-009.1 + US-009.2 chiuse)
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
| 2 | **US-009.2** Reskilling Infrastructure | [#45](https://github.com/giamma80/profilebot/issues/45) | 5 | ✅ Done | — | `feature/US-009.2-reskilling` |
| 3 | **US-009.3** KP Schema e Builder Base | [#46](https://github.com/giamma80/profilebot/issues/46) | 5 | 🟡 In Progress | US-009.1 ✅, US-009.2 ✅ | `feature/US-009.3-kp-builder` |
| 4 | **TD-001** Connector Contract (starter) | [#47](https://github.com/giamma80/profilebot/issues/47) | 3 | 🔵 To Do | — | `feature/TD-001-connector-contract` |
| 5 | **TD-004** Resilience Base (metrics + CB) | [#48](https://github.com/giamma80/profilebot/issues/48) | 3 | 🔵 To Do | — | `feature/TD-004-resilience-base` |
| | **TOTALE** | | **18** | **7 done** | | |

---

## Sequenza di Lavoro Aggiornata

US-009.1 e US-009.2 sono completate e mergiate su `main`. Il piano aggiornato:

```
Week 1 (completata)
├── US-009.1 Seniority Calculator ────── ✅ Done (giorno 1-2)
└── US-009.2 Reskilling Infrastructure ─ ✅ Done (giorno 2-3)
    └── Skill Dictionary v2 merge ────── ✅ Done (1210 skill, 786 alias)

Week 2 (giorni 4-10, corrente)
├── US-009.3 KP Schema e Builder ──────── [giorno 4-6] 🟡 In Progress
├── TD-001 Connector Contract ─────────── [giorno 4-5] (parallelizzabile)
├── TD-004 Resilience Base ────────────── [giorno 5-6] (parallelizzabile)
└── Review + fix + merge ──────────────── [giorno 7-8]
```

### Critical Path

```
US-009.1 (seniority) ✅ ──┐
                           ├──→ US-009.3 (KP Builder) 🟡 ──→ SPRINT GOAL ✅
US-009.2 (reskilling) ✅ ──┘

TD-001 e TD-004 sono indipendenti e parallelizzabili con US-009.3.
```

> **Nota:** Tutte le dipendenze di US-009.3 sono soddisfatte. Il critical path è sbloccato.

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

### ✅ US-009.2 — Reskilling Infrastructure (5 SP) — COMPLETATA

**Obiettivo:** Layer completo per consumare dati di reskilling via REST API dallo scraper service, normalizzarli, cacharli in Redis e servirli al KP Builder.

**Risultato:**

- `src/services/reskilling/schemas.py` — `ReskillingRecord(BaseModel)` + `ReskillingStatus(StrEnum)` con valori `IN_PROGRESS/COMPLETED/PLANNED`
- `src/services/reskilling/normalizer.py` — mapping campi SharePoint raw → Pydantic, log warning su campi sconosciuti
- `src/services/reskilling/cache.py` — `ReskillingCache` Redis con TTL configurabile
- `src/services/reskilling/service.py` — `ReskillingService` con get/get_bulk/filter/refresh + read-through cache
- `src/services/scraper/client.py` — `fetch_reskilling_row(res_id)` integrato
- `data/skills_dictionary.yaml` aggiornato a v2.0.0 (1210 skill, 786 alias, 22 domini)
- PR mergiata su `main`

**Nota per US-009.3:** `ReskillingRecord` ha `skill_target: str | None` (singolo, non lista). `ReskillingStatus` usa `IN_PROGRESS` (non `ACTIVE`). Il Builder deve adattarsi ai tipi reali, non al design doc §3.2.

---

### US-009.3 — KP Schema e Builder Base (5 SP) — 🟡 IN PROGRESS

**Obiettivo:** Modello `KnowledgeProfile` unificato che assembla dati da 4 sorgenti (Qdrant, availability, reskilling, dictionary).

**Dipendenze — tutte soddisfatte:** US-009.1 ✅, US-009.2 ✅, Skill Dictionary v2 ✅. Non servono mock/stub.

**Deliverable:**

- `src/core/knowledge_profile/schemas.py` — `KnowledgeProfile` + sotto-modelli: `SkillDetail`, `AvailabilityDetail`, `ReskillingPath`, `ExperienceSnapshot`, `RelevantChunk`, `ICSubState(StrEnum)`
- `src/core/knowledge_profile/ic_sub_state.py` — `calculate_ic_sub_state()` (None / ic_available / ic_in_reskilling / ic_in_transition)
- `src/core/knowledge_profile/builder.py` — `KPBuilder` con constructor injection, graceful degradation per ogni sorgente
- `src/core/knowledge_profile/serializer.py` — `KPContextSerializer` + `estimate_tokens()` (len/4)
- Test: ≥ 8 test cases (IC sub-state ×4, builder ×3, serializer ×2)

**⚠️ Attenzione delta design doc:** Lo schema in `docs/LLM-study.md` §3.2 è stato scritto prima di US-009.2. Differenze critiche: `ReskillingRecord.skill_target` è `str | None` (non `list[str]`), `ReskillingStatus` usa `IN_PROGRESS/COMPLETED/PLANNED` (non `ACTIVE/DROPPED`), `ic_sub_state` va nel KP top-level (non dentro AvailabilityDetail). Dettagli completi nella [issue #46](https://github.com/giamma80/profilebot/issues/46) aggiornata.

**Rischi:** Basso (ridotto da medio-alto). Tutte le dipendenze sono soddisfatte, le interfacce dei servizi sono stabili.

**Ref:** `docs/LLM-study.md` §3, §7, §9, §10 | Issue [#46](https://github.com/giamma80/profilebot/issues/46) aggiornata

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
- [x] Reskilling layer consuma dati esclusivamente via REST API dello scraper service (✅ US-009.2)
- [ ] KP Builder assembla profilo completo con dati reali o mock
- [ ] Documentazione aggiornata (BACKLOG.md, OpenAPI ref dello scraper service)

---

## Metriche di Successo

| Metrica | Target | Attuale |
|---------|--------|---------|
| SP completati | ≥ 15/18 (83%) | 7/18 (39%) |
| Issue chiuse | ≥ 4/5 | 2/5 |
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

*Ultimo aggiornamento: 1 marzo 2026*
