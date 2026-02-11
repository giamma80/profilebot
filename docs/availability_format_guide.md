# Availability Format Guide (Canonical CSV)

Questo documento descrive il **formato canonico CSV** per la disponibilità, usato dal servizio Availability (US-007).  
Le sorgenti (connector) devono **produrre questo CSV**, non importare direttamente da sistemi esterni.

---

## ✅ Canonical CSV Header

Il file CSV **deve** includere **esattamente** queste colonne (in qualunque ordine):

```
res_id,status,allocation_pct,current_project,available_from,available_to,manager_name,updated_at
```

### Significato colonne

| Colonna | Tipo | Obbligatoria | Descrizione |
|---------|------|---------------|-------------|
| `res_id` | int | ✅ | Matricola/ID risorsa. Deve essere numerico. |
| `status` | enum | ✅ | Stato disponibilità: `free`, `partial`, `busy`, `unavailable` |
| `allocation_pct` | int | ✅ | Percentuale allocazione (0–100). |
| `current_project` | string | ⬜ | Nome progetto attuale (vuoto se free). |
| `available_from` | date | ⬜ | Data disponibilità (ISO 8601: `YYYY-MM-DD`). |
| `available_to` | date | ⬜ | Data fine disponibilità (ISO 8601: `YYYY-MM-DD`). |
| `manager_name` | string | ⬜ | Nome del responsabile (opzionale). |
| `updated_at` | datetime | ✅ | Timestamp aggiornamento (ISO 8601). |

---

## ✅ Valori ammessi per `status`

```
free         # Completamente disponibile
partial      # Allocato parzialmente (1-99%)
busy         # Allocato su progetto (100%)
unavailable  # Non disponibile (ferie, malattia, cessato)
```

---

## ✅ Esempio valido

```csv
res_id,status,allocation_pct,current_project,available_from,available_to,manager_name,updated_at
100000,free,0,,,,,2026-02-10T08:00:00Z
100001,partial,40,ProjectAlpha,,,Manager Uno,2026-02-10T08:00:00Z
100002,busy,100,ProjectBeta,,,Manager Due,2026-02-10T08:00:00Z
100003,unavailable,0,,2026-03-01,2026-03-31,,2026-02-10T08:00:00Z
100004,free,0,,,,,2026-02-10T08:00:00Z
```

---

## ❌ Regole di validazione

Una riga viene **scartata** se:

- `res_id` non è un intero valido  
- `status` non è tra i valori ammessi  
- `allocation_pct` non è un intero tra 0 e 100  
- `updated_at` non è un datetime ISO 8601 valido

---

## ✅ Note su encoding

- Encoding richiesto: **UTF‑8**
- Separatore: **comma** `,`
- Header obbligatorio

---

## ✅ Responsabilità

- **Connector esterni** → producono CSV canonico
- **Availability service** → carica CSV e lavora solo su questo formato

---