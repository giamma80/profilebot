
# Appendice tecnica — Indexing, Context Management e Parametri LLM

## A. Algoritmi di indexing vettoriale

### A.1 Perché l’indexing è critico

In un sistema con ~10.000 CV, l’indexing:

* non è un dettaglio implementativo
* **influenza direttamente precisione, latenza e stabilità**
* deve essere **prevedibile e riproducibile**

Il vector store non è un database tradizionale:
usa **Approximate Nearest Neighbors (ANN)**.

---

### A.2 Algoritmo consigliato: HNSW

Per Qdrant (e sistemi analoghi), l’algoritmo di riferimento è:

**HNSW – Hierarchical Navigable Small World**

Caratteristiche:

* ricerca sub-lineare
* ottimo trade-off precisione / performance
* stabile su dataset medi (10k–1M vettori)

Perché è adatto al tuo caso:

* workload read-heavy
* K ridotti (20–50)
* dataset che cresce nel tempo
* supporta filtri metadata senza degrado grave

---

### A.3 Implicazioni architetturali (da sapere)

* L’index è **approssimato**, non esatto
* Due query identiche possono restituire:

  * stesso set
  * ordine leggermente diverso

👉 **Non basare decisioni finali sull’ordine del ranking vettoriale**
👉 Usare la vector search **solo per shortlist**

---

### A.4 Antipattern di indexing

* usare vector score come punteggio finale
* confrontare score tra collection diverse
* ri-indicizzare spesso per dati volatili

---

## B. Context normalization e augmentation

### B.1 Cos’è il “context” nel tuo sistema

Il contesto è **l’input cognitivo dell’LLM**, non:

* il risultato del retrieval
* né l’intero CV

Ma:

> **una rappresentazione controllata, normalizzata e intenzionale**

---

### B.2 Context normalization (obbligatoria)

Obiettivi:

* ridurre rumore
* eliminare ambiguità
* rendere confrontabili i CV

Tecniche concettuali:

* ordine fisso delle sezioni
* stesso schema per ogni CV
* lessico normalizzato (skill dal dizionario)

Esempio logico:

1. Skill normalizzate (sempre prima)
2. Esperienze rilevanti (dopo)
3. Altre informazioni (opzionali)

👉 La normalizzazione **vale più dell’embedding**.

---

### B.3 Context augmentation (controllata)

L’augmentation NON è:

* aggiungere informazioni inventate
* inferire skill non presenti

È:

* **arricchire con informazioni strutturali**
* rendere esplicito ciò che è già implicito

Esempi leciti:

* associare una esperienza a una skill già dichiarata
* esplicitare seniority se presente nel testo
* raggruppare esperienze simili

Esempi illeciti:

* dedurre skill non dichiarate
* inferire capacità “probabili”
* usare conoscenza esterna non tracciata

---

### B.4 Regola d’oro

> **Il contesto può essere riorganizzato e chiarito,
> ma mai “migliorato semanticamente”.**

---

## C. Parametri LLM: temperatura, token, source

#### C.1 Temperatura

Nel tuo sistema l’LLM:

* non crea contenuti creativi
* prende decisioni spiegate

👉 **Temperatura consigliata: bassa (0.0 – 0.3)**

Motivo:

* output stabile
* spiegazioni ripetibili
* auditabilità

Temperatura alta = variabilità = rischio HR.

---

### C.2 Token management

Principi:

* il contesto deve stare **comodamente** sotto il limite
* il modello deve avere spazio per ragionare

Strategia:

* limitare il numero di CV completi (5–7 max)
* chunk brevi e densi
* preferire liste a testo narrativo

👉 Se tagli token a caso, **tagli il ragionamento**.

---

### C.3 Source attribution (fondamentale)

Ogni affermazione dell’LLM deve poter essere ricondotta a:

* CV_ID
* sezione (skill / experience)
* chunk o elemento

Non serve citazione verbosa, ma:

* riferimento strutturale
* tracciabile nei log

Esempio concettuale:

> “La scelta è basata sulle skill X e Y presenti nel CV_ID=123, sezione Skill.”

---

### C.4 Antipattern LLM

* temperature alte “per sembrare più intelligenti”
* prompt lunghi e non strutturati
* contesto non omogeneo tra CV
* mancanza di riferimenti alle fonti

---

## Collegamento con workflow `res_id`
Per l’orchestrazione delle fonti e l’allineamento con il flusso di ingestione basato su `res_id`, fare riferimento a:
- `docs/res_id-workflow.md`

## Principio finale di chiusura

> **La qualità del sistema non dipende dal modello,
> ma da come indicizzi, normalizzi e controlli il contesto.**
