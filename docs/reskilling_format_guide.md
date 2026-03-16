# Reskilling RowResponse — Format Guide

> **Scope:** Questo documento descrive il formato JSON restituito dallo scraper service
> (`GET /reskilling/csv/{res_id}`) e il mapping verso il modello Pydantic
> `ReskillingRecord`.

---

## 1. RowResponse (Scraper Service)

L’endpoint restituisce un JSON con questa struttura:

```/dev/null/row_response.json#L1-L10
{
  "res_id": "210513",
  "row": {
    "Risorsa:Consultant ID": "210513",
    "Risorsa": "Donnemma, Debora",
    "Nome Corso": "Kubernetes Fundamentals",
    "Stato": "In Progress",
    "Percentuale Completamento": "75%"
  }
}
```

- `res_id`: identificativo risorsa (stringa).
- `row`: oggetto **dinamico** (additionalProperties = true). I campi dipendono dal tracciato SharePoint.

---

## 2. Modello Canonico (Pydantic)

```/dev/null/reskilling_record.py#L1-L30
class ReskillingRecord(BaseModel):
    res_id: int
    course_name: str
    skill_target: str | None
    status: ReskillingStatus
    start_date: date | None
    end_date: date | None
    provider: str | None
    completion_pct: int | None
```

**ReskillingStatus** (StrEnum):
- `in_progress`
- `completed`
- `planned`

---

## 3. Mapping campi (SharePoint → Pydantic)

Il normalizer cerca **più alias** per ogni campo. I nomi qui sotto sono
quelli riconosciuti oggi; eventuali campi non mappati vengono loggati come warning
e ignorati.

| Campo Pydantic | Alias riconosciuti (case‑insensitive) |
|---|---|
| `res_id` | `Risorsa:Consultant ID`, `Consultant ID`, `ResID`, `res_id` |
| `course_name` | `Nome Corso`, `Titolo Corso`, `Corso`, `Course Name`, `Course`, `Training`, `Percorso`, `course_name` |
| `skill_target` | `Skill Target`, `Target Skill`, `Competenza`, `Competenza Target`, `Skill`, `skill_target` |
| `status` | `Stato`, `Status`, `Course Status` |
| `start_date` | `Data Inizio`, `Start Date`, `Inizio`, `start_date` |
| `end_date` | `Data Fine`, `End Date`, `Fine`, `end_date` |
| `provider` | `Provider`, `Training Provider`, `Ente`, `Fornitore` |
| `completion_pct` | `Percentuale Completamento`, `Completion %`, `Completion`, `Completion Pct`, `Percentuale`, `completion_pct` |

---

## 4. Normalizzazione valori

### Status
Valori supportati (case‑insensitive):
- `in_progress`
- `completed`
- `planned`

Sinonimi normalizzati:
- `in progress`, `ongoing` → `in_progress`
- `done`, `finished` → `completed`
- `scheduled` → `planned`

Valori sconosciuti ⇒ **skip della riga** + warning.

### Date
- Formato atteso: `YYYY-MM-DD`
- Accettati timestamp `YYYY-MM-DDTHH:MM:SSZ` (troncati a data)
- Valori non validi ⇒ campo `None` (non blocca la riga)

### completion_pct
Accettati:
- interi (`75`)
- stringhe con percentuale (`"75%"`)
- float `0-1` (`0.75` → `75`)

Valori non validi ⇒ campo `None`.

---

## 5. Esempi

### Riga valida
```/dev/null/reskilling_valid.json#L1-L12
{
  "res_id": "210513",
  "row": {
    "Risorsa:Consultant ID": "210513",
    "Nome Corso": "Kubernetes Fundamentals",
    "Skill Target": "kubernetes",
    "Stato": "Completed",
    "Data Inizio": "2025-10-01",
    "Data Fine": "2026-01-15",
    "Provider": "CloudAcademy",
    "Percentuale Completamento": "100%"
  }
}
```

### Riga malformata (status sconosciuto)
```/dev/null/reskilling_invalid.json#L1-L9
{
  "res_id": "210513",
  "row": {
    "Risorsa:Consultant ID": "210513",
    "Nome Corso": "Kubernetes Fundamentals",
    "Stato": "paused"
  }
}
```
**Esito:** riga **skippata** + warning.

---

## 6. Note operative

- Il normalizer è **l’unico punto di accoppiamento** con il tracciato SharePoint.
- I campi non riconosciuti vengono **loggati** e ignorati.
- Se `res_id`, `course_name` o `status` mancano o sono invalidi, la riga viene **scartata**.
