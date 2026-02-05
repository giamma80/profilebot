
# Sistema di CV Matching skill-first con RAG, Qdrant e gestione disponibilitÃ 

## Documento di sintesi architetturale e funzionale

---

## 1. Premessa

Lâ€™obiettivo del sistema Ã¨ **identificare il profilo professionale piÃ¹ adatto** a una posizione, a partire da:

- un corpus di ~10.000 CV
- una fonte esterna di **stato operativo** (disponibilitÃ  / allocazione)
- un **dizionario di skill normalizzate**

Il sistema:

- NON Ã¨ un motore di ricerca generico
- NON Ã¨ un classificatore ML supervisionato
- Ãˆ un **sistema decisionale guidato**, basato su:
  - filtri deterministici
  - similaritÃ  semantica
  - ragionamento LLM spiegabile

---

## 2. Strategia generale (principi non negoziabili)

### 2.1 Separazione dei ruoli

| Componente | Ruolo |
|----------|------|
| Dizionario skill | Normalizzazione semantica |
| Metadata | Controllo e filtraggio |
| Vector search | Shortlist semantica |
| LLM | Decisione e spiegazione |
| Stato operativo | Vincolo di dominio |

Nessun componente deve fare il lavoro di un altro.

---

### 2.2 Skill-first

- **Skill** = segnale decisionale primario
- **Esperienze** = segnale di supporto
- **DisponibilitÃ ** = vincolo di accesso

---

### 2.3 Stato â‰  Conoscenza

- Le skill sono **conoscenza stabile**
- La disponibilitÃ  Ã¨ **stato volatile**
â†’ devono vivere in **store separati**

---

## 3. Architettura logica complessiva

```

```

            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚  SharePoint List   â”‚
            â”‚ (DisponibilitÃ )    â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                      â”‚

```

Client (Chatbot)           â–¼
â”‚             Operational State Store
â”‚                     â”‚
â–¼                     â–¼
Backend RAG API â”€â”€â”€â”€â–º Filtro DisponibilitÃ 
â”‚                     â”‚
â–¼                     â–¼
Filtro Metadata (skill_domain, seniority)
â”‚
â–¼
Qdrant â€“ cv_skills (vector search)
â”‚
â–¼
Shortlist cv_id
â”‚
â–¼
Qdrant â€“ cv_experiences (supporto)
â”‚
â–¼
Costruzione contesto
â”‚
â–¼
OpenAI (LLM)
â”‚
â–¼
Decisione spiegata

```

---

## 4. Flusso decisionale end-to-end

### Step 0 â€” Input

- skill richieste (normalizzate)
- dominio
- seniority
- vincoli di disponibilitÃ 

---

### Step 1 â€” Filtro disponibilitÃ  (deterministico)

Fonte: SharePoint scraper  
Chiave: `cv_id`

- only_free
- free_or_partial
- any

Se nessun CV Ã¨ disponibile â†’ **stop e risposta esplicita**.

---

### Step 2 â€” Filtro metadata

Riduzione dominio:

- `skill_domain`
- `seniority_bucket`
- presenza skill minime

---

### Step 3 â€” Vector search sulle skill

- **solo collection `cv_skills`**
- K medio (20â€“50)
- output: shortlist `cv_id`

---

### Step 4 â€” Experience enrichment

- **solo per i cv_id shortlistati**
- K piccolo per CV
- solo contesto di supporto

---

### Step 5 â€” Decisione LLM

- confronto profili
- prioritÃ  alle skill
- esperienze come conferma
- output spiegato

---

## 5. Formule e schemi concettuali

### 5.1 Dominio di ricerca

```

D0 = tutti i CV
D1 = CV disponibili
D2 = CV compatibili per dominio/seniority
D3 = CV skill-matchati
D4 = CV spiegabili

```

Ogni step **riduce lâ€™incertezza**, mai il contrario.

---

### 5.2 Regola su K

- K_skill < K_experience
- skill globali, experience per-CV
- LLM vede max 5â€“7 CV completi

---

## 6. Moduli di intelligenza semantica e NLP

### 6.1 Moduli necessari (librerie concettuali)

| Modulo | Scopo |
|-----|-----|
| Parsing CV | Estrazione strutturata |
| Skill extraction | Regex + LLM vincolato |
| Skill normalization | Mapping su dizionario |
| Embedding | SimilaritÃ  semantica |
| LLM reasoning | Decisione e spiegazione |

---

### 6.2 Uso corretto dellâ€™LLM

- SÃŒ: estrarre, mappare, spiegare
- NO: cercare, inferire skill mancanti, decidere disponibilitÃ 

---

## 7. Dizionario delle skill

### 7.1 Caratteristiche

- vocabolario chiuso
- versionato
- normalizza, non arricchisce

Esempi:

- `PM` â†’ `project_management`
- `ISTQB` â†’ `software_testing`
- `Spring` â†’ `java_backend`

---

### 7.2 Regole

- se non mappa â†’ `unknown`
- nessuna skill inventata
- mapping con confidence

---

## 8. Struttura delle Collection Qdrant

### 8.1 Collection `cv_skills`

Contiene:

- embedding delle skill
- pochi chunk
- alta densitÃ  semantica

**Metadata obbligatori**

- `cv_id`
- `section_type = skill`
- `normalized_skills`
- `skill_domain`
- `dictionary_version`

---

### 8.2 Collection `cv_experiences`

Contiene:

- embedding delle esperienze
- chunk descrittivi

**Metadata obbligatori**

- `cv_id`
- `section_type = experience`
- `related_skills` (se presenti)

---

### 8.3 Cosa NON va in Qdrant

- disponibilitÃ 
- stato operativo
- dati volatili

---

## 9. Ingestion pipeline (concettuale)

```

CV
â†“
Redis Queue
â†“
Worker Python
â†“
Parsing
â†“
Skill extraction
â†“
Normalizzazione (dizionario)
â†“
Embedding
â†“
Upsert Qdrant

```

Pipeline:

- deterministica
- idempotente
- ri-eseguibile

---

## 10. Prompting: struttura e contenuti

### 10.1 System Prompt (base)

> Sei un assistente per il matching professionale.  
> La selezione deve basarsi **principalmente sulle skill**.  
> Le esperienze servono solo come supporto.  
> Tutti i profili forniti sono giÃ  **disponibili** e validi.  
> Non inferire skill non dichiarate.  
> Restituisci sempre il `cv_id` e una motivazione.

---

### 10.2 Prompt di contesto (dinamico)

Struttura:

1. Skill per CV (prima)
2. Esperienze per CV (dopo)

Formato consigliato:

```

CV_ID: X
SKILLS:

* â€¦
  EXPERIENCES (support):
* â€¦

```

---

### 10.3 User Prompt (task)

> Dato il contesto fornito:
>
> - identifica il profilo piÃ¹ adatto
> - motiva la scelta dando prioritÃ  alle skill
> - indica eventuali gap rilevanti

---

## 11. Output atteso (contratto funzionale)

### Output minimo

- `selected_cv_id`
- `decision_reason`

### Output esteso

- skill matchate
- skill mancanti
- esperienze rilevanti
- confidence qualitativa (high / medium / low)

---

## 12. Antipattern critici da evitare

- CV come documento unico
- similarity-only ranking
- disponibilitÃ  gestita dallâ€™LLM
- metadata descrittivi inutilizzabili
- embedding usati come spiegazione

---

## 13. Principi conclusivi

1. **La disponibilitÃ  decide chi puÃ² partecipare**
2. **Le skill decidono chi vince**
3. **Lâ€™LLM decide solo alla fine**
4. **Se non Ã¨ spiegabile, Ã¨ progettato male**

---

## Destinatari

Questo documento Ã¨ destinato a:

- analisti funzionali
- solution architect
- tech lead
- sviluppatori backend
- data engineer
- data scientist
- product owner
- stakeholder di business
- team di QA
- team di supporto tecnico
