# Issue: Ingestion freshness refactor (Phase 2)

## Contesto
La fase 1 introduce freshness gate per `res_id`, idempotenza e delete-by-res_id.
Riferimento: `docs/issues/issue-ingestion-freshness.md`.
Questa fase 2 completa il refactoring architetturale: spostare tutta la logica di ingest
su un endpoint API atomico per singolo `res_id`, e alleggerire il workflow Celery.

## Related issues
- `docs/issues/issue-ingestion-freshness.md` (phase 1)

## Obiettivo
- Incapsulare l’intero ciclo di ingest in una **API atomica per `res_id`**.
- Eliminare job “grandi” (batch) dal workflow, usando fanout per item.
- Rendere il workflow più resiliente e scalabile via coda.

## Nuovo flusso (alta livello)
1. Celery fanout per `res_id`.
2. Per ogni `res_id`: task Celery chiama l’API atomica.
3. L’API gestisce end‑to‑end:
   - freshness gate (skip se fresco)
   - delete per `res_id`
   - download CV
   - parsing
   - embedding (skills/experiences/chunks)
   - upsert Qdrant
   - set freshness key

## Cambiamento workflow
Il workflow in `config/workflows/res_id_workflow.yaml` viene snellito:
- mantiene `scraper.fetch_inside_res_ids`
- mantiene il fanout per `res_id`
- **rimuove** il callback globale `embedding.index_from_scraper`
- il fanout richiama un task per‑item che delega all’API atomica

Risultato: niente chord “lunghe” e niente callback batch, ogni `res_id` è indipendente.

## API atomica (entry point unico)
- Endpoint: `POST /api/v1/ingestion/res-id/{res_id}`
- Query param: `force=false` (bypass freshness)
- Response: `status`, `detail`, `res_id`, `cv_id`, `counts`, `deleted`

La logica è la stessa descritta in fase 1, ma **centralizzata qui**.

## Celery (nuovo task per item)
- Task: `ingestion.process_res_id`
- Responsabilità: chiamare l’API atomica
- Retry: solo su errori temporanei (HTTP 5xx / network)

## Touchpoints previsti
- `config/workflows/res_id_workflow.yaml`
- `src/services/embedding/tasks.py` (rimozione uso batch nel workflow)
- `src/api/v1` (nuovo endpoint ingestion)
- `src/core` (funzioni di delete-by-res_id già definite in fase 1)
- `src/services/scraper` (client download CV, invariato)

## Rischi / Note
- I task per‑item aumentano il volume in coda: verificare `CELERY_WORKER_CONCURRENCY`.
- Possibile rate limit verso `scraper-service` e LLM embeddings.
- Necessari log chiari per `status=skipped` (fresh).

## Done when
- Il workflow non usa più callback batch.
- Esiste l’API atomica e viene usata dal task per‑item.
- Qdrant viene popolato anche con fanout ampio, senza timeout dei chord.
- Freshness gate e delete-by-res_id restano applicati come in fase 1.