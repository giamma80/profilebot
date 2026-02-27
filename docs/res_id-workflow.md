# Studio architettura workflow res_id (Celery + DAG config)

## Obiettivo
Definire un workflow modulare per l’ingestione di fonti dati legate a `res_id`, mantenendo **Celery come motore di esecuzione** ma introducendo un **DAG dichiarativo** configurato in JSON/YAML per consentire:
- aggiunta di nuove fonti senza cambiare codice orchestration;
- evoluzione graduale verso pipeline più complesse;
- riuso di task e logica di retry/observability già esistente.

---

## Contesto
Lo scraper fornisce **3 fonti principali**:
1. Inside CV (`/inside/res-ids`, fan‑out su `/inside/cv/{res_id}`)
2. Availability CSV (`/availability/csv`)
3. Reskilling CSV (`/reskilling/csv`)

Nel prossimo futuro potrebbero arrivare nuove fonti o step di arricchimento.  
Serve quindi un layer di orchestration **espandibile** ma leggero.

---

## Decisione
### ✅ Celery come executor
- già presente nello stack
- task già versionati e schedulati
- compatibile con retry e logging

### ✅ DAG dichiarativo
- definito in file JSON/YAML (es. `config/workflows/res_id_workflow.yaml`)
- caricato a runtime e trasformato in chain/group/chord Celery
- consente di aggiungere nodi senza codice

---

## Concetto di DAG (config)
Ogni nodo rappresenta un **task Celery** con:
- `id` univoco
- `task` (stringa importabile Celery)
- `depends_on` (lista di nodi)
- `params` (payload statico)
- `fanout` opzionale (es: fan‑out su lista `res_ids`)
- `retry_policy` override opzionale

### Esempio (YAML)
```/dev/null/res_id_workflow.yaml#L1-L40
version: 1
workflow_id: res_id_ingestion
schedule: "0 */4 * * *"

nodes:
  - id: fetch_res_ids
    task: src.services.scraper.tasks.scraper_inside_refresh_task

  - id: inside_fanout
    task: src.services.workflows.tasks.run_workflow_fanout_task
    depends_on: [fetch_res_ids]
    fanout:
      source: redis:profilebot:scraper:inside:res_ids
      task: src.services.scraper.tasks.scraper_inside_refresh_item_task
      parameter_name: res_id

  - id: export_availability
    task: src.services.scraper.tasks.scraper_availability_csv_refresh_task

  - id: export_reskilling
    task: src.services.scraper.tasks.scraper_reskilling_csv_refresh_task
```

---

## Orchestrazione dinamica
### Caricamento
1. Leggere YAML/JSON da path noto
2. Validare schema (pydantic)
3. Creare grafo in memoria
4. Trasformare in chain/group

### Strategia di esecuzione
- nodi **senza dipendenze** → `group()`
- nodi con dipendenze → `chain()` o `chord()`
- eventuale fan‑out → generazione task dinamici

---

## Fan‑out su `res_id`
Nel caso Inside CV:
1. task `fetch_res_ids` recupera lista e la scrive in Redis
2. DAG può avere un nodo “fan‑out” che legge la lista e genera task child:
```/dev/null/fanout_example.yaml#L1-L20
  - id: inside_fanout
    task: src.services.workflows.tasks.run_workflow_fanout_task
    depends_on: [fetch_res_ids]
    fanout:
      source: redis:profilebot:scraper:inside:res_ids
      task: src.services.scraper.tasks.scraper_inside_refresh_item_task
      parameter_name: res_id
```

Questa separazione permette:
- riuso del `res_id` cache
- aggiunta futura di nuove pipeline che usano la stessa lista

---

## Evoluzione futura
Con nuove fonti si aggiunge un nodo e (eventualmente) un link di dipendenza, senza modificare l’orchestratore.

### Esempio: “assessment” aggiuntivo
```/dev/null/extra_source.yaml#L1-L10
  - id: export_assessment
    task: src.services.scraper.tasks.scraper_assessment_csv_refresh_task
    depends_on: [export_availability]
```

---

## Osservabilità
- ogni task logga `workflow_id`, `node_id`, `status`
- Flower già presente per visibilità runtime
- possibile estensione con `task_annotations` per rate‑limit

---

## Schema Pydantic (proposta)
Modello minimale per validare il DAG dichiarativo.

```/dev/null/workflow_schema.py#L1-L60
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

class FanoutConfig(BaseModel):
    source: str
    task: str
    parameter_name: str

class RetryPolicy(BaseModel):
    max_retries: int = Field(default=3, ge=0)
    countdown: int = Field(default=60, ge=0)

class WorkflowNode(BaseModel):
    id: str
    task: str
    depends_on: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    fanout: FanoutConfig | None = None
    retry_policy: RetryPolicy | None = None

class WorkflowDefinition(BaseModel):
    version: int = 1
    workflow_id: str
    schedule: str | None = None
    nodes: list[WorkflowNode]
```

---

## Directory layout consigliato
Struttura chiara per file di workflow e runner.

```/dev/null/workflow_layout.txt#L1-L20
config/
  workflows/
    res_id_workflow.yaml
    res_id_workflow.dev.yaml

src/
  core/
    workflows/
      loader.py
      runner.py
      schemas.py
```

---

## Loader (validazione) — esempio
Esempio di caricamento e validazione del workflow da YAML/JSON con Pydantic.

```/dev/null/workflow_loader_example.py#L1-L40
from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.core.workflows.schemas import WorkflowDefinition

def load_workflow(path: Path) -> WorkflowDefinition:
    raw = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        payload = yaml.safe_load(raw)
    else:
        payload = json.loads(raw)
    return WorkflowDefinition.model_validate(payload)
```

---

## WorkflowRunner — pseudocodice
Conversione del DAG in primitive Celery (`group`, `chain`, `chord`).

```/dev/null/workflow_runner_pseudocode.py#L1-L60
def run_workflow(definition):
    nodes = index_by_id(definition.nodes)
    graph = build_dependency_graph(nodes)

    def build_task(node):
        signature = celery.signature(node.task, kwargs=node.params)
        if node.retry_policy:
            signature.set(
                retries=node.retry_policy.max_retries,
                countdown=node.retry_policy.countdown,
            )
        return signature

    roots = [n for n in nodes if not n.depends_on]
    if not roots:
        raise ValueError("Workflow has no root nodes")

    parallel_roots = group(build_task(n) for n in roots)

    return parallel_roots  # or chain/chord based on dependencies
```

---

## Mapping nodi DAG ↔ task Celery esistenti
Tabella di riferimento per collegare i nodi del DAG ai task già disponibili.

| Nodo DAG (id) | Task Celery | Note |
| --- | --- | --- |
| fetch_res_ids | src.services.scraper.tasks.scraper_inside_refresh_task | Recupera res_id, fan‑out interno, cache su Redis |
| inside_fanout | src.services.workflows.tasks.run_workflow_fanout_task | Esegue fan‑out su res_id cached e lancia refresh per item |
| export_availability | src.services.scraper.tasks.scraper_availability_csv_refresh_task | Export CSV availability |
| export_reskilling | src.services.scraper.tasks.scraper_reskilling_csv_refresh_task | Export CSV reskilling |

---

## Impatti su altri documenti in docs
Se introduciamo il DAG dichiarativo, alcuni documenti potrebbero richiedere aggiornamento per coerenza:

- `docs/USER_STORIES_DETAILED.md`: se la US‑016 deve includere il DAG dichiarativo o la logica di orchestrazione.
- `docs/BACKLOG.md`: per inserire attività su loader/runner o gestione workflow config.
- `docs/CONTRIBUTING.md`: se servono istruzioni su come aggiungere nuovi nodi al DAG.
- `docs/analisi_preliminare.md`: per riflettere l’evoluzione dell’architettura di ingestione.
- `docs/appendice_tecnica_indexing.md`: se il processo di ingestione influisce sul flusso di indicizzazione.
- `docs/technical_debt.md`: se l’orchestrazione custom introduce debito tecnico o decisioni da tracciare.

---

## Trade‑off
### Pro
- basso overhead
- incrementale
- compatibile con struttura attuale

### Contro
- orchestrazione custom
- meno features native rispetto a Prefect/Airflow

---

## Raccomandazione operativa
1. Implementare un loader `WorkflowDefinition` (Pydantic)
2. Introdurre un `WorkflowRunner` che converte il DAG in Celery primitives
3. Introdurre un file `res_id_workflow.yaml`
4. Collegare il schedule Celery alla definizione del workflow

---

## Output attesi
- Pipeline dichiarativa per `res_id`
- Aggiunta fonti future senza refactor
- Esecuzione stabile ogni 4h con Celery