# ProfileBot Runbook — Pipeline Alerting

## Overview
Questo runbook descrive come interpretare e rispondere agli alert della pipeline ProfileBot. Le regole sono definite in `config/monitoring/alerts/profilebot.yml` e instradate tramite Alertmanager (`config/monitoring/alertmanager/alertmanager.yml`).

### Severity & Priorità
- **P1 / critical**: azione immediata, alert su Slack.
- **P2 / warning**: degradazione o rischio; alert su Slack raggruppati.
- **P3 / info**: solo log (no Slack).

## Alert Routing
Alertmanager è configurato per:
- **P1**: notifiche immediate (Slack).
- **P2**: raggruppate ogni 15 minuti (Slack).
- **P3**: log-only.

### Slack Webhook
Impostare in `.env`:
- `SLACK_WEBHOOK_URL=<webhook-url>`

Alertmanager usa `--config.expand-env` per espandere la variabile.

## Validation & Checks
- Prometheus rules:
  - `promtool check rules config/monitoring/alerts/profilebot.yml`
- Alertmanager config:
  - `amtool check-config config/monitoring/alertmanager/alertmanager.yml`

## Grafana
Il dashboard `ProfileBot / Processing Pipeline` include il pannello **Active Alerts**.

## Alerts & Actions

### P1 — Critical
#### ProfileBotTaskStalled
**Sintomo:** task avviati ma non completati da >10m.  
**Azioni:**
1. Verificare `celery_task_started_total` vs `celery_task_succeeded_total` + `celery_task_failed_total`.
2. Controllare `flower` e code Redis.
3. Verificare log worker Celery e blocchi di I/O.

#### ProfileBotErrorRateSpike
**Sintomo:** failure rate >5% su 5m.  
**Azioni:**
1. Identificare task con `celery_task_failed_total` per `name/exception`.
2. Verificare dipendenze esterne (Scraper/Qdrant/Redis).
3. Se persistente, attivare mitigazione (rate limit, retry, circuit-breaker).

#### ProfileBotRedisQueueOverflow
**Sintomo:** `redis_db_keys{db="db0"} > 1000`.  
**Azioni:**
1. Verificare backlog Celery/queue length.
2. Valutare scaling worker.
3. Pulire chiavi obsolete se necessario.

---

### P2 — Warning
#### ProfileBotTaskLatencyHigh
**Sintomo:** p95 runtime > 300s.  
**Azioni:**
1. Identificare task più lenti.
2. Verificare timeout e chiamate esterne.
3. Considerare splitting o batch più piccoli.

#### ProfileBotQdrantVectorDrift
**Sintomo:** variazione vettori >10% in 1h.  
**Azioni:**
1. Verificare pipeline di embedding.
2. Controllare ingestion duplicata o drop massivo.
3. Verificare job di reindexing (se presenti).

#### ProfileBotRetryStorm
**Sintomo:** retry rate elevato (celery).  
**Azioni:**
1. Identificare task con retry.
2. Verificare cause di failure transiente.
3. Se ripetuto, ridurre rate limit o intervenire su dipendenza.

#### ProfileBotScraperDLQ
**Sintomo:** eventi DLQ (task `scraper.refresh_inside_profile_dlq`).  
**Azioni:**
1. Verificare log per `res_id` falliti.
2. Valutare retry manuale per res_id critici.
3. Analizzare cause (timeout scraper, invalid payload).

---

### P3 — Info
#### ProfileBotPipelineCompletion
**Sintomo:** pipeline ingestion completata con successo.  
**Azioni:** nessuna, solo monitoraggio.

#### ProfileBotPartialChord
**Sintomo:** `celery_chord_partial_success_total` incrementata.  
**Azioni:**
1. Consultare log `workflow.log_failed_profiles`.
2. Valutare retry mirato sui `res_id` falliti.

## DLQ Handling
I task che superano i retry vengono inviati al task:
- `scraper.refresh_inside_profile_dlq`  
Output atteso: `{status: "dlq", res_id, error, error_type}`.

## Freshness Gate (Ingestion)
La pipeline blocca re-ingestion dello stesso `res_id` entro la TTL configurata (`FRESHNESS_TTL_SECONDS`, default 43200s).  
Chiave Redis: `profilebot:freshness:{res_id}`.

**Sintomo:** log con "Skipping CV due to freshness gate".  
**Azioni:**
1. Verificare presenza chiave: `redis-cli GET profilebot:freshness:{res_id}`.
2. Se serve forzare re-ingestion, cancellare la chiave: `redis-cli DEL profilebot:freshness:{res_id}`.
3. Controllare eventuali failure a monte prima di rimuovere il gate.

## LLM Section Classification
La classificazione LLM delle sezioni CV è disattivata di default.  
Feature flag: `LLM_SECTION_CLASSIFICATION_ENABLED` (default `false`).  
Prompt versionato: `data/prompts/section_classification.yaml`.

**Sintomo:** parsing CV fallisce con errore di classificazione LLM.  
**Azioni:**
1. Verificare log applicativi per il dettaglio dell’errore.
2. Validare il prompt e l’output JSON atteso.
3. Se serve stabilità immediata, disattivare il flag e ripetere l’ingestion del singolo CV.

## Escalation
Se un P1 non rientra entro 15 minuti:
- Escalare al team Ops e bloccare temporaneamente nuove ingestion.
