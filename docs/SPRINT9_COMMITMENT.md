# Sprint 9 Commitment — Pipeline Stabilization

> **Sprint:** 9
> **Milestone GitHub:** Sprint 9 - Pipeline Stabilization
> **Durata:** 2 settimane (7 mar – 21 mar 2026)
> **Velocity target:** 18 SP (media storica: ~20 SP/sprint)
> **Tema:** Risolvere il bug P0 nella pipeline di ingestion, implementare resilienza ai fallimenti parziali, e chiudere il ciclo di observability con alerting proattivo

---

## Sprint Goal

**Stabilizzare la pipeline di ingestion ProfileBot eliminando il bug P0 #65** (`scraper.inside_refresh` loop sincrono) e costruendo l'infrastruttura di resilienza e alerting necessaria a garantire dati affidabili in Qdrant.

Al termine dello sprint:
- Il task `inside_refresh` sarà decomposto in operazioni atomiche e resilienti
- I fallimenti parziali nella pipeline non bloccheranno più l'intero workflow
- Prometheus genererà alert proattivi per anomalie nella pipeline
- Il test e2e di US-009.4 sarà completabile con dati consistenti

---

## Contesto e Motivazione

### Il problema

Lo Sprint 8 (Observability Stack) ha fatto emergere un **difetto architetturale critico**: il task Celery `scraper.inside_refresh` contiene un loop sincrono che processa TUTTI i profili (~100) in sequenza. Questo causa:

1. **Timeout a ~500s** con retry dall'inizio, perdendo tutto il lavoro fatto
2. **Doppia elaborazione**: il fanout successivo ricrea gli stessi task individuali
3. **Dati inconsistenti in Qdrant**: payload incompleti o duplicati

Questo bug (#65, P0-critical) **blocca di fatto** sia #54 (KP Context — integration test e2e) che #63 (Fallback semantico skill), perché entrambi dipendono da dati Qdrant consistenti.

### La catena di risoluzione

```
#68 TD-007 (Best-Effort Chord)     ← prerequisito pattern
        ↓
#67 TD-006 (Fix inside_refresh)    ← risolve #65, 3 fasi
        ↓
#69 OBS-066 (Alerting Rules)       ← monitora la pipeline post-fix
        ↓
#54 completamento test e2e         ← sbloccato da dati consistenti
```

### Riferimenti architetturali

- `docs/ProfileBot_Architecture_Analysis.md` §2.2, §4.5.2 (Fetch/Refresh Decoupling)
- `docs/LLM-study.md` §2.1, §3.3 (KP population dipende da dati Qdrant affidabili)
- ADR-003 (Best-Effort Chord pattern)
- ADR-004 (Observability Stack)

---

## Stato Issue

| # | Issue | GitHub | SP | Priorità | Dipendenze | Branch proposto |
|---|-------|--------|----|----------|------------|-----------------|
| 1 | **TD-007** Best-Effort Chord | [#68](https://github.com/giamma80/profilebot/issues/68) | 5 | P0 | — | `feature/TD-007-best-effort-chord` |
| 2 | **TD-006** Fix scraper.inside_refresh | [#67](https://github.com/giamma80/profilebot/issues/67) | 8 | P0 | TD-007 (Fase 2) | `feature/TD-006-inside-refresh-fix` |
| 3 | **OBS-066** Prometheus Alerting Rules | [#69](https://github.com/giamma80/profilebot/issues/69) | 3 | P1 | PR #62 (mergiata) | `feature/OBS-066-alerting-rules` |
| 4 | **US-009.4** Completamento test e2e | [#54](https://github.com/giamma80/profilebot/issues/54) | 2 | P1 | TD-006 | branch esistente |
| | **TOTALE** | | **18** | | | |

**Bug di riferimento:** [#65](https://github.com/giamma80/profilebot/issues/65) — [BUG][P0] scraper.inside_refresh: loop sincrono non resiliente

---

## Sequenza di Lavoro

```
Week 1 (giorni 1-5)
├── TD-007 Best-Effort Chord ──────────── [giorno 1-3]
│   ├── BestEffortChord class
│   ├── Collector per risultati + errori
│   ├── min_success_ratio parameter
│   └── Test unitari
│
└── TD-006 Fase 1: Decoupling ─────────── [giorno 3-5]
    ├── Separare inside_refresh in fetch_res_ids + refresh_single_cv
    ├── Fanout genera refresh_single_cv per ogni res_id
    └── Test: ogni task indipendente, fallimento isolato

Week 2 (giorni 6-10)
├── TD-006 Fase 2: Best-Effort Chord ──── [giorno 6-7]
│   ├── Integrare BestEffortChord nel workflow
│   └── embed_all procede con risultati parziali
│
├── TD-006 Fase 3: Retry Granulare ────── [giorno 7-8]
│   ├── Exponential backoff per refresh_single_cv
│   └── max_retries=3, retry_backoff=True, retry_backoff_max=120
│
├── OBS-066 Alerting Rules ─────────────── [giorno 8-9]
│   ├── prometheus/alerts/profilebot.yml (P1 + P2 + P3)
│   ├── Alertmanager routing configuration
│   └── Grafana "Active Alerts" panel
│
└── US-009.4 Completamento test e2e ────── [giorno 9-10]
    └── Integration test pipeline JD → search → KP → LLM
```

### Critical Path

```
TD-007 (chord) ──→ TD-006 Fase 2 ──→ TD-006 Fase 3 ──→ US-009.4 (test e2e)
                        ↑
              TD-006 Fase 1 (decoupling)

OBS-066 è indipendente, richiede solo PR #62 (già mergiata)
```

---

## Dettaglio per Issue

### TD-007 — Best-Effort Chord: pattern Celery tollerante ai fallimenti parziali (5 SP)

**Obiettivo:** Implementare un custom Celery chord che proceda con i risultati disponibili anche se alcuni task del gruppo falliscono.

**Deliverable:**

- `app/tasks/patterns.py` — classe `BestEffortChord` con `on_error` callback
- Collector che raccoglie sia risultati che errori
- Callback invocato quando tutti i task terminano (successo o failure)
- Il callback riceve `(results: list, errors: list)` anziché solo `results`
- Parametro `min_success_ratio` (default 0.8): procedi se ≥ 80% dei task ha successo
- Log esplicito dei `res_id` falliti per retry successivo

**Esempio di utilizzo target:**
```python
# Invece di:
chord(group_of_tasks)(callback)  # Fallisce se anche 1 task fallisce

# Usiamo:
best_effort_chord(group_of_tasks)(
    callback,
    min_success_ratio=0.8  # Procedi se >= 80% dei task hanno successo
)
```

**File coinvolti:** `app/tasks/patterns.py` (nuovo), `tests/test_patterns.py` (nuovo)

**Acceptance Criteria:**
- [ ] Chord procede con risultati parziali se `min_success_ratio` è soddisfatto
- [ ] Chord fallisce esplicitamente se sotto la soglia
- [ ] Errori loggati con dettaglio `res_id` e tipo errore
- [ ] Metrica Prometheus `celery_chord_partial_success_total`
- [ ] ≥ 5 test unitari (happy path, soglia, errore totale, boundary)

**Ref:** `docs/ProfileBot_Architecture_Analysis.md` ADR-003

---

### TD-006 — Fix scraper.inside_refresh: decoupling fetch/refresh e retry granulare (8 SP)

**Obiettivo:** Decomporre il monolite `inside_refresh` in operazioni atomiche, resilienti e osservabili. Risolve il bug P0 #65.

**3 Fasi di implementazione:**

**Fase 1 — Decoupling Fetch/Refresh (giorni 3-5):**
- Separare `inside_refresh` in due task distinti:
  - `fetch_res_ids`: solo recupero lista `res_id` (leggero, <5s)
  - `refresh_single_cv(res_id)`: refresh + download di un singolo CV
- Il fanout genera un `refresh_single_cv` per ogni `res_id`
- Ogni task è indipendente: se uno fallisce, gli altri continuano

**Fase 2 — Best-Effort Chord (giorni 6-7):**
- Integrare `BestEffortChord` (da TD-007) nel workflow
- Il chord raccoglie i risultati disponibili e procede con `embed_all`
- Log esplicito dei `res_id` falliti per retry successivo

**Fase 3 — Retry Granulare (giorni 7-8):**
- Configurare retry con exponential backoff per `refresh_single_cv`:
  - `max_retries=3`, `retry_backoff=True`, `retry_backoff_max=120`
- Dead Letter Queue per task definitivamente falliti
- Metrica Prometheus per retry count per `res_id`

**File coinvolti:** `app/tasks/scraper.py`, `app/tasks/workflows.py`, `res_id_workflow.yaml`, `docker-compose.yml`, `tests/test_scraper.py`

**Acceptance Criteria:**
- [ ] `inside_refresh` non contiene più loop sincroni
- [ ] Singolo CV failure non blocca la pipeline
- [ ] Timeout per singolo task < 30s (vs ~500s attuale)
- [ ] Metriche per-task visibili su Grafana
- [ ] Il workflow completo termina in < 5 minuti (vs timeout attuale)
- [ ] Test di regressione: simulare 5% failure rate, verificare pipeline completion

**Ref:** `docs/ProfileBot_Architecture_Analysis.md` §2.2, §4.5.2, ADR-004

---

### OBS-066 — Prometheus Alerting Rules per pipeline ProfileBot (3 SP)

**Obiettivo:** Configurare regole di alerting Prometheus per ricevere notifiche proattive quando la pipeline presenta anomalie.

**Regole di alerting proposte:**

| Priorità | Regola | Condizione PromQL | Azione |
|----------|--------|-------------------|--------|
| P1 | Task Stalled | `celery_task_started_total - celery_task_succeeded_total - celery_task_failed_total > 0` per >10min | Slack immediato |
| P1 | Error Rate Spike | `rate(celery_task_failed_total[5m]) / rate(celery_task_received_total[5m]) > 0.05` | Slack immediato |
| P1 | Redis Queue Overflow | `redis_db_keys{db="db0"} > 1000` | Slack immediato |
| P2 | Task Latency | `histogram_quantile(0.95, celery_task_runtime_seconds_bucket) > 300` | Slack raggruppato 15min |
| P2 | Qdrant Drift | Variazione improvvisa nel count dei punti (>10% in 1h) | Slack raggruppato 15min |
| P2 | Retry Storm | `rate(celery_task_retries_total[5m]) > 0.1` | Slack raggruppato 15min |
| P3 | Pipeline Completion | Workflow completato con successo | Log only |
| P3 | Partial Chord | Best-effort chord con fallimenti parziali | Log only |

**File coinvolti:** `prometheus/alerts/profilebot.yml` (nuovo), `prometheus/prometheus.yml` (aggiunta `rule_files`), `alertmanager/alertmanager.yml` (routing), `docker-compose.yml` (mount volumes), `grafana/dashboards/profilebot-processing.json` (pannello alerts), `docs/runbook.md`

**Acceptance Criteria:**
- [ ] Le 3 regole P1 generano alert entro 2 minuti dall'anomalia
- [ ] Le regole P2 generano alert raggruppati entro 15 minuti
- [ ] Alertmanager routing funziona (testato con `amtool`)
- [ ] `promtool check rules` passa senza errori
- [ ] Dashboard Grafana include pannello "Active Alerts"
- [ ] Documentazione delle soglie in `docs/runbook.md`

**Ref:** `docs/ProfileBot_Architecture_Analysis.md` ADR-004, PR #62

---

### US-009.4 — Completamento test e2e (2 SP)

**Obiettivo:** Completare l'integration test end-to-end della pipeline JD → search → KP → CandidateMatch, bloccato dalla dipendenza su dati Qdrant consistenti.

**Prerequisito:** TD-006 completato (dati Qdrant affidabili post-fix)

**Deliverable:**
- Integration test che valida l'intero flusso: query JD → skill normalize → vector search → KP assembly → LLM decision
- Mock dei servizi esterni (LLM, scraper) per determinismo
- Fixture con dati sintetici rappresentativi
- Verifica che il KP builder produce profili completi con seniority, availability, reskilling

**Acceptance Criteria:**
- [ ] Test e2e passa su CI
- [ ] Coverage della pipeline ≥ 80%
- [ ] Nessuna checkbox aperta rimasta nella issue

---

## Definition of Done (Sprint-level)

- [ ] Tutte le issue hanno PR approvata e mergiata su `main`
- [ ] Test passano su CI (ruff + pytest)
- [ ] Coverage ≥ 80% sui nuovi moduli
- [ ] `scraper.inside_refresh` non contiene più loop sincroni
- [ ] Pipeline completa in < 5 minuti con 100 profili
- [ ] Singolo failure non blocca il workflow
- [ ] Alert P1 funzionanti su Slack
- [ ] `docs/runbook.md` con procedure di risposta agli alert
- [ ] Dashboard Grafana aggiornata con pannello alerting

---

## Metriche di Successo

| Metrica | Target | Baseline (pre-sprint) |
|---------|--------|-----------------------|
| SP completati | ≥ 15/18 (83%) | 0 |
| Pipeline completion time | < 5 min | ~500s + timeout |
| Single CV failure isolation | 100% | 0% (cascade failure) |
| Alert P1 response time | < 2 min | ∞ (nessun alert) |
| Test e2e passing | ✅ | ❌ (bloccato da #65) |

---

## Rischi e Mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|:-:|:-:|-------------|
| BestEffortChord complesso da integrare con Celery internals | Media | Alto | Prototype first, fallback su `group().apply_async()` con callback manuale |
| Retry granulare genera troppe richieste allo scraper | Bassa | Medio | Rate limiting con `celery.rate_limit`, max 10 req/s |
| Alert troppo rumorosi (false positives) | Media | Basso | Soglie conservative iniziali, tuning nella prima settimana |
| TD-006 richiede più di 8 SP | Bassa | Alto | Le 3 fasi sono rilasciabili indipendentemente; Fase 1 da sola risolve il P0 |

---

## Dipendenze Esterne

- **PR #62** (Observability Stack): già mergiata su `main` — prerequisito per OBS-066
- **Scraper Service REST API**: nessun cambiamento richiesto — i task chiamano le stesse API
- **Docker Compose**: aggiornamento per mount `prometheus/alerts/` e configurazione Alertmanager

---

## Cosa NON è nello scope

- #63 (Fallback semantico skill) — sbloccata da questo sprint, pianificata per Sprint 10
- #15 (Source Attribution) — Sprint Current ma non in commitment Sprint 9
- #57 (TD-005 Automazione Embedding) — Sprint Current, non prioritario
- UI (US-011, US-012) — Backlog
- Migrazione a Prefect/Dagster — future sprint
- Aggiornamento `LLM-study.md` — nota tecnica, non bloccante

---

## Post-Sprint: cosa abilita

Con la pipeline stabilizzata, gli sprint successivi potranno:

1. **#63 Fallback semantico** — chunk search su dati Qdrant consistenti e completi
2. **#15 Source Attribution** — KP traccia le sorgenti con dati affidabili
3. **Multi-scenario prompting** (LLM-study.md §6) — il KP builder produce profili di qualità
4. **Scalabilità** — la pipeline atomica scala linearmente con il numero di profili
5. **Monitoring proattivo** — alert automatici riducono il tempo di risposta agli incidenti

---

*Ultimo aggiornamento: 7 marzo 2026*
