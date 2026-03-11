# Issue: Ingestion freshness gate per res_id (12h) — Phase 1

## Contesto
Durante i match emergono più CV dello stesso candidato (stesso `res_id` con `cv_id` diversi).  
Questo indica che ogni ingest genera un nuovo `cv_id` e scrive nuovi punti in Qdrant.

## Evidenze (Qdrant status al momento della verifica)
- Collezioni presenti: `cv_skills`, `cv_experiences`
- `cv_skills`
  - `points_count`: 456
  - `indexed_vectors_count`: 0
  - `status`: green
- `cv_experiences`
  - `points_count`: 4308
  - `indexed_vectors_count`: 3341
  - `status`: green

## Flusso di ingest attuale
Workflow principale (configurato in `config/workflows/res_id_workflow.yaml`):
1. `scraper.fetch_inside_res_ids`
2. `workflow.fanout_by_res_id` → `scraper.refresh_inside_profile` (per ogni `res_id`)
3. Callback: `embedding.index_from_scraper` (download CV + parsing + indexing)

Entry-point alternativi:
- `embedding.index_cv`
- `embedding.index_cv_batch`
- `embedding.index_all_cvs`

## Root cause
`cv_id` viene generato in base a timestamp (da `build_cv_id()`), quindi ad ogni parsing:
- nuovo `cv_id`
- nuovi point id in Qdrant
- duplicati per `res_id`

Non esiste un gate di freshness, quindi i CV vengono riprocessati anche se già “freschi”.

## Obiettivo
Fase 1: bloccare il processing in entrata per `res_id` già indicizzati entro una finestra di 12 ore.  
Se non fresco, il CV deve essere riprocessato e **sovrascrivere totalmente** le informazioni esistenti.

## Scope (Phase 1)
- Freshness gate e lock Redis.
- Idempotenza con delete-by-res_id prima del nuovo upsert.

## Fase 2 (refactoring)
La fase 2 sposta l’ingest per `res_id` su API atomica e snellisce il workflow.  
Vedi `docs/issues/issue-ingestion-freshness-2.md`.

## Related issues
- `docs/issues/issue-ingestion-freshness-2.md` (phase 2)

## Proposed behavior (AC)
- Per ogni task che prende in carico un CV (tutti gli entry-point sopra):
  1. check freshness su `res_id`
  2. se “fresco” → skip ingest (log + metrica)
  3. se “stale” → procedi, **cancella i dati precedenti** per `res_id` e reindicizza
- TTL freshness: 12 ore

## Implementazione proposta
### 1) Lock + Freshness gate (Redis)
Obiettivo: evitare enqueue di task inutili e prevenire doppie lavorazioni.
- Lock key: `profilebot:ingestion:lock:res_id:{res_id}` (TTL breve, es. 10 minuti)
- Fresh key: `profilebot:ingestion:fresh:res_id:{res_id}` (TTL 12 ore)

Flow consigliato:
1. **Pre-enqueue**: `SETNX lock` → se fallisce, skip enqueue
2. Worker/API processa
3. **On success**: `SET fresh EX 12h` e delete lock

### 2) Idempotenza e sovrascrittura completa
Il worker/API deve essere idempotente:
- delete per `res_id` su tutte le collezioni Qdrant in uso (`cv_skills`, `cv_experiences`, `cv_chunks` se presente)
- successivo upsert del nuovo contenuto

### 3) API REST per processing singolo res_id (decoupling)
Questa parte è rimandata alla fase 2 del refactoring.  
Vedi `docs/issues/issue-ingestion-freshness-2.md`.

### 4) Touchpoints
- `workflow.fanout_by_res_id`: applicare il gate **prima** dell’enqueue (snellimento workflow in fase 2)
- `src/services/embedding/tasks.py`:
  - `embed_cv_task`
  - `embed_batch_task`
  - `embed_all_task`
  - `embed_from_scraper_task`

## Note / Questioni aperte
- Confermare che `cv_chunks` è attiva in produzione (ora non risulta tra le collezioni).
- Definire logging/metriche per: `skipped_fresh`, `reprocessed_stale`, `deleted_by_res_id`.
- È necessario un flag `force` per bypassare il gate (es. reindex massivo)?
