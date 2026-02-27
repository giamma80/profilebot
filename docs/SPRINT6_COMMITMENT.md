# Sprint 6 Commitment — KP Foundation

> **Sprint:** 6
> **Milestone GitHub:** Sprint 6 - KP Foundation
> **Durata:** 2 settimane (27 feb – 13 mar 2026)
> **Velocity target:** 18 SP (media storica: ~22 SP/sprint)
> **Tema:** Costruire le fondamenta del Knowledge Profile per abilitare decisioni LLM multi-scenario

---

## Sprint Goal

**Sbloccare il Knowledge Profile (KP) come modello dati unificato per l'LLM**, implementando le 3 sorgenti dati mancanti (seniority calcolata, reskilling, KP assembly) e iniziando il consolidamento dell'infrastruttura di ingestion (connector contract, resilience).

Al termine dello sprint, il sistema sarà in grado di assemblare un KP completo per qualsiasi profilo e fornirlo come contesto strutturato all'LLM.

---

## Issue Committed

| # | Issue | GitHub | SP | Owner | Dipendenze | Branch |
|---|-------|--------|----|-------|------------|--------|
| 1 | **US-009.1** Seniority Calculator | [#44](https://github.com/giamma80/profilebot/issues/44) | 2 | — | nessuna | `feature/US-009.1-seniority` |
| 2 | **US-009.2** Reskilling Infrastructure | [#45](https://github.com/giamma80/profilebot/issues/45) | 5 | — | nessuna | `feature/US-009.2-reskilling` |
| 3 | **US-009.3** KP Schema e Builder Base | [#46](https://github.com/giamma80/profilebot/issues/46) | 5 | — | US-009.1, US-009.2 | `feature/US-009.3-kp-builder` |
| 4 | **TD-001** Connector Contract (starter) | [#47](https://github.com/giamma80/profilebot/issues/47) | 3 | — | nessuna | `feature/TD-001-connector-contract` |
| 5 | **TD-004** Resilience Base (metrics + CB) | [#48](https://github.com/giamma80/profilebot/issues/48) | 3 | — | nessuna | `feature/TD-004-resilience-base` |
| | **TOTALE** | | **18** | | | |

---

## Sequenza di Lavoro Consigliata

```
Week 1 (giorni 1-5)
├── US-009.1 Seniority Calculator ─────── [giorno 1-2] ⬅️ START HERE
├── TD-001 Connector Contract ─────────── [giorno 2-3] (parallelizzabile)
├── TD-004 Resilience Base ────────────── [giorno 3-4] (parallelizzabile)
└── US-009.2 Reskilling Infrastructure ── [giorno 3-5]

Week 2 (giorni 6-10)
├── US-009.2 completamento + test ─────── [giorno 6-7]
├── US-009.3 KP Schema e Builder ──────── [giorno 7-9] (dopo 009.1 + 009.2)
└── Review + fix + merge ──────────────── [giorno 9-10]
```

### Critical Path

```
US-009.1 (seniority) ──┐
                        ├──→ US-009.3 (KP Builder) ──→ SPRINT GOAL ✅
US-009.2 (reskilling) ─┘

TD-001 e TD-004 sono indipendenti e parallelizzabili.
```

---

## Dettaglio per Issue

### US-009.1 — Seniority Calculator (2 SP)

**Obiettivo:** Calcolare `seniority_bucket` deterministico da esperienze e skill, eliminando l'hardcode `"unknown"`.

**Deliverable:**
- `src/core/seniority/calculator.py` — euristica basata su years_exp + skill_count + role_keywords
- Integrazione in `EmbeddingPipeline` (rimuove hardcode)
- Payload Qdrant aggiornato
- 4+ test cases (junior, mid, senior, lead, unknown)

**Rischi:** Basso. Euristica deterministica, scope contenuto.

---

### US-009.2 — Reskilling Infrastructure (5 SP)

**Obiettivo:** Layer completo per caricare, validare, cachare e servire i dati di reskilling da CSV.

**Deliverable:**
- Schema `ReskillingRecord` + `ReskillingStatus`
- CSV loader con validazione e skip righe malformate
- `ReskillingService` con Redis cache (TTL configurabile)
- Celery task `refresh_reskilling_cache`
- Format guide in `docs/reskilling_format_guide.md`

**Rischi:** Medio. Il formato CSV reale potrebbe avere edge case non previsti. Mitigazione: loader robusto con skip + log.

---

### US-009.3 — KP Schema e Builder Base (5 SP)

**Obiettivo:** Modello `KnowledgeProfile` unificato che assembla dati da 4 sorgenti (Qdrant, availability, reskilling, dictionary).

**Deliverable:**
- Schema `KnowledgeProfile` con sezioni: identity, skills, seniority, experiences, availability, ic_sub_state, reskilling
- `ICSubStateCalculator` (not_ic / ic_available / ic_in_reskilling / ic_in_transition)
- `KPBuilder` service (assembly dalle 4 sorgenti)
- `KPContextSerializer` (output strutturato per prompt LLM)
- Token budget estimator

**Rischi:** Medio-alto. Dipende da US-009.1 e US-009.2. Se una delle due ritarda, il KP Builder può essere sviluppato con mock/stub e integrato dopo.

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

---

### TD-004 — Resilience Base (3 SP)

**Obiettivo:** Metriche ingestion strutturate + circuit breaker base.

**Deliverable:**
- `IngestionMetrics` con contatori per source_type (Redis-backed)
- Decoratore `@track_ingestion` per task Celery
- `CircuitBreaker` state machine (closed → open → half_open)
- Endpoint GET `/api/v1/metrics/ingestion`

**Rischi:** Basso. Pattern noti, scope contenuto. Il circuit breaker è una state machine semplice.

---

## Definition of Done (Sprint-level)

- [ ] Tutte le issue hanno PR approvata e mergiata su `main`
- [ ] Test passano su CI (ruff + pytest)
- [ ] Coverage ≥ 80% sui nuovi moduli
- [ ] Nessun hardcode `"unknown"` residuo per seniority
- [ ] KP Builder assembla profilo completo con dati reali o mock
- [ ] Documentazione aggiornata (BACKLOG.md, format guide)

---

## Metriche di Successo

| Metrica | Target |
|---------|--------|
| SP completati | ≥ 15/18 (83%) |
| Issue chiuse | ≥ 4/5 |
| Test aggiunti | ≥ 25 nuovi test |
| Coverage nuovi moduli | ≥ 80% |

---

## Dipendenze Esterne

Nessuna dipendenza esterna bloccante. Tutti i dati necessari (CSV reskilling, CV DOCX) sono già accessibili tramite lo scraper service.

---

## Cosa NON è nello scope

- US-010 (Source Attribution) — spostata a Sprint 5 - UI (milestone esistente)
- US-008 completamento AC mancanti — merge in corso su Sprint 4
- Prefect/Dagster setup (TD-005 Fase 2) — future sprint
- UI (US-011, US-012) — Sprint 5 - UI

---

## Post-Sprint: cosa abilita

Con il KP Foundation completato, gli sprint successivi potranno:
1. **Multi-scenario prompting** — matching, gap analysis, reskilling suggestion usano lo stesso KP
2. **Source Attribution (US-010)** — il KP traccia da dove viene ogni dato
3. **Chat Interface (US-011)** — il KP è il contesto per la conversazione
4. **Reskilling Suggestion scenario** — il prompt può ragionare su corsi in corso e gap colmabili
