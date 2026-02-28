# LLM Study — Knowledge Profile & Multi-Scenario AI Integration

> Vademecum tecnico-architetturale per l'integrazione LLM in ProfileBot.
> Questo documento analizza in profondità il modello Knowledge Profile (KP),
> la strategia di prompting multi-scenario, e la roadmap implementativa
> per trasformare ProfileBot da sistema di ricerca skill-based a piattaforma
> di decisione AI-assisted.

**Versione:** 1.0
**Data:** 2026-02-27
**Autore:** Solution Architect (Claude) + Giamma
**Riferimenti:** analisi_preliminare.md §2.2, §6.2, §8, §10; US-009; SPRINT4_COMMITMENT.md

---

## Indice

1. [Contesto e Motivazione](#1-contesto-e-motivazione)
2. [Stato Attuale del Sistema](#2-stato-attuale-del-sistema)
3. [Il Modello Knowledge Profile (KP)](#3-il-modello-knowledge-profile-kp)
4. [Le 4 Sorgenti Dati](#4-le-4-sorgenti-dati)
5. [Strategia Hybrid Context: Strutturato + Chunk](#5-strategia-hybrid-context-strutturato--chunk)
6. [Multi-Scenario Prompting](#6-multi-scenario-prompting)
7. [IC (Intercontratto) e Sotto-Stati](#7-ic-intercontratto-e-sotto-stati)
8. [Reskilling: Infrastruttura Mancante e Design](#8-reskilling-infrastruttura-mancante-e-design)
9. [Architettura del Context Builder](#9-architettura-del-context-builder)
10. [Token Budget e Ottimizzazione](#10-token-budget-e-ottimizzazione)
11. [Prompt Engineering per Scenario](#11-prompt-engineering-per-scenario)
12. [Gap Analysis del Codebase Attuale](#12-gap-analysis-del-codebase-attuale)
13. [Roadmap Implementativa](#13-roadmap-implementativa)
14. [Antipattern e Rischi](#14-antipattern-e-rischi)
15. [Appendice: Schema Dati Completo](#15-appendice-schema-dati-completo)

---

## 1. Contesto e Motivazione

ProfileBot nasce come sistema di ricerca profili basato su skill matching vettoriale. L'architettura attuale segue il principio **skill-first** definito in analisi_preliminare.md §2.2:

> **Skills = segnale decisionale primario → Esperienze = supporto → Disponibilità = vincolo di accesso**

Questo approccio funziona bene per la ricerca: data una Job Description (JD), il sistema trova i profili con le skill più vicine tramite embedding similarity su Qdrant. Ma la ricerca è solo il primo passo.

Il vero valore emerge quando un LLM può **ragionare** sui risultati: non solo "chi ha queste skill?" ma "chi è il candidato migliore considerando esperienza, disponibilità, percorso di reskilling, e copertura dei gap?". Questo richiede un modello dati ricco — il **Knowledge Profile (KP)** — che aggreghi tutte le informazioni disponibili su un profilo in un formato che l'LLM possa consumare efficacemente.

### 1.1 Perché non basta il vector search

Il vector search su Qdrant restituisce un ranking per similarità coseno. Ma:

- **Non distingue** tra una skill posseduta al 90% di confidence (match esatto dal dizionario) e una al 60% (fuzzy match) — il vettore embedding è una media.
- **Non vede** la disponibilità reale: un profilo perfetto allocato al 100% su un progetto è inutile per una staffing request.
- **Non conosce** i percorsi di reskilling in corso: una risorsa IC che sta completando un corso su Kubernetes potrebbe essere più adatta di una risorsa con Kubernetes dichiarato nel CV ma non praticato da anni.
- **Non ragiona** su combinazioni: per staffare un team di 3 persone servono skill complementari, non 3 profili identici.

L'LLM colma questi gap, ma solo se riceve il contesto giusto.

### 1.2 Il principio di analisi_preliminare.md §6.2

Il documento fondativo è chiaro:

> L'LLM non deve essere usato per classificare skill o embeddings. Il suo ruolo è la **decisione finale** su candidati pre-filtrati, con contesto strutturato.

Questo principio architetturale guida l'intero studio: l'LLM riceve candidati già filtrati (top-K da vector search) e arricchiti (KP completo), e produce una decisione motivata. Non sostituisce il vector search — lo completa.

---

## 2. Stato Attuale del Sistema

### 2.1 Pipeline CV: dal file al vettore

```
PDF/DOCX → Parser → ParsedCV → SkillExtractor → NormalizedSkills
                                                        ↓
                                            EmbeddingPipeline
                                                ↓           ↓
                                          cv_skills    cv_experiences
                                          (Qdrant)      (Qdrant)
```

**Parser** (`src/core/parser/`):
- `section_detector.py`: regex per identificare sezioni (skills, experience, education, certifications)
- `metadata_extractor.py`: euristica per nome, ruolo corrente
- Output: `ParsedCV` con metadata, skills (raw_text + skill_keywords), experiences, education, certifications, raw_text

**Skill Extraction** (`src/core/skills/`):
- `dictionary.py`: dizionario YAML versionato con canonical name, domain, aliases, related skills, certifications
- `normalizer.py`: normalizzazione via exact match → alias match → fuzzy match
- Output: `NormalizedSkill` con original, canonical, domain, confidence, match_type

**Embedding Pipeline** (`src/core/embedding/pipeline.py`):
- **cv_skills**: un singolo vettore per profilo = embedding della stringa "Python, FastAPI, PostgreSQL, ..." (skill canoniche concatenate)
- **cv_experiences**: un vettore per ogni experience = embedding della description di ogni esperienza lavorativa
- Payload cv_skills: `{cv_id, res_id, normalized_skills[], skill_domain[], seniority_bucket, dictionary_version}`
- Payload cv_experiences: `{cv_id, res_id, related_skills[], experience_years}`

**Problema critico**: `seniority_bucket` è hardcoded a `"unknown"` (pipeline.py linea ~149). Non è mai stato implementato il calcolo della seniority.

### 2.2 Ricerca: dal query all'elenco candidati

```
JD skills query → SkillNormalizer → Embedding → Qdrant search(cv_skills)
                                                        ↓
                                               Availability filter (Redis)
                                                        ↓
                                               Scoring (similarity × 0.7 + match_ratio × 0.3)
                                                        ↓
                                               List[ProfileMatch]
```

**ProfileMatch** contiene: `res_id, cv_id, score, matched_skills, missing_skills, skill_domain, seniority`.

Questo è l'input attuale per l'LLM — ma è insufficiente. Manca tutto il contesto che rende una decisione davvero informata.

### 2.3 Disponibilità: stack completo

```
Scraper → CSV export → AvailabilityLoader → Redis cache
                                                ↓
                                         AvailabilityService
                                         (get, get_bulk, filter)
```

La disponibilità ha un'infrastruttura matura:
- **Schema**: `ProfileAvailability` (res_id, status, allocation_pct, current_project, available_from, available_to, manager_name, updated_at)
- **Status enum**: free, partial, busy, unavailable
- **Cache**: Redis con TTL configurabile
- **Loader**: validazione CSV canonico, skip delle righe invalide
- **Service**: filtri per mode (only_free, free_or_partial, unavailable)

### 2.4 Reskilling: il buco architetturale

> **⚠️ AGGIORNAMENTO (Sprint 6):** Il pattern è stato cambiato da CSV a REST API. Lo scraper service espone endpoint REST che restituiscono JSON per singolo res_id. Vedi §8 per il design aggiornato.

```
Scraper REST API (GET /reskilling/csv/{res_id}) → JSON → ???
```

Lo scraper ha gli endpoint REST per i dati di reskilling (OpenAPI: GET/POST `/reskilling/csv`, GET `/reskilling/csv/{res_id}` che restituisce JSON `{res_id, row}`), e il Celery task `scraper_reskilling_csv_refresh_task` esiste per il trigger export. **Ma ProfileBot non ha nessuna infrastruttura per consumare questi dati**: nessuno schema, nessun normalizer, nessun cache, nessun service. È il gap più critico per il KP model.

### 2.5 LLM Layer attuale (US-009 parziale)

```
src/core/llm/
├── __init__.py
├── client.py      # LLMDecisionClient + create_llm_client factory
├── prompts.py     # build_system_prompt, build_context, parse_decision_output
└── schemas.py     # LLMRequest, DecisionCandidate, DecisionOutput
```

`DecisionCandidate` attuale è troppo scarno:
```python
class DecisionCandidate(BaseModel):
    cv_id: str
    skills: list[str]              # solo nomi canonici, senza metadata
    seniority: str                 # sempre "unknown"
    years_experience: int | None
    availability_status: str       # solo il label, perde allocation_pct
    experience_summaries: list[str]
```

Il context builder formatta ogni candidato come blocco di testo piatto, senza struttura semantica che aiuti l'LLM a ragionare sui dettagli.

---

## 3. Il Modello Knowledge Profile (KP)

Il Knowledge Profile è il **modello dati composito** che aggrega tutte le informazioni disponibili su un profilo per fornire all'LLM il contesto necessario alla decisione. Non è un nuovo database — è una vista di aggregazione costruita on-demand per i candidati pre-filtrati.

### 3.1 Principi di design

1. **Skill-centric ma non skill-only**: le skill restano il segnale primario, ma con metadata ricchi (domain, confidence, fonte, recency)
2. **Availability come vincolo, non filtro**: l'LLM deve vedere lo stato completo, non solo "available sì/no"
3. **Reskilling come potenziale**: le skill in acquisizione sono valore futuro, l'LLM deve poterle pesare
4. **Chunk come evidenza**: i chunk dal CV forniscono il contesto narrativo che i dati strutturati non catturano
5. **Token-aware**: il KP deve essere serializzabile in modo efficiente per rispettare il budget token

### 3.2 Struttura proposta

```python
class SkillDetail(BaseModel):
    """Skill con metadata completi per il KP."""
    canonical: str                          # nome canonico dal dizionario
    domain: str                             # backend|frontend|data|devops|management
    confidence: float                       # 0.0-1.0 dal normalizer
    match_type: Literal["exact", "alias", "fuzzy"]
    source: Literal["cv", "reskilling"]     # da dove viene questa skill
    reskilling_completion_pct: int | None    # se source=reskilling, % completamento
    related_certifications: list[str]       # certificazioni collegate dal dizionario
    last_used_hint: str | None              # euristica da experiences

class AvailabilityDetail(BaseModel):
    """Disponibilità completa per il KP."""
    status: AvailabilityStatus              # free|partial|busy|unavailable
    allocation_pct: int                     # 0-100
    current_project: str | None
    available_from: date | None
    available_to: date | None
    manager_name: str | None
    is_intercontratto: bool                 # allocation_pct == 0 e status in (free, unavailable)
    ic_sub_state: Literal[                  # sotto-stato IC
        "ic_available",                     # IC e disponibile
        "ic_in_reskilling",                 # IC con percorso formativo attivo
        "ic_in_transition",                 # IC in fase di transizione/colloqui
        None                                # non IC
    ]

class ReskillingPath(BaseModel):
    """Percorso di reskilling attivo o completato."""
    course_name: str
    target_skills: list[str]                # skill canoniche obiettivo
    completion_pct: int                     # 0-100
    provider: str | None                    # ente formativo
    start_date: date | None
    end_date: date | None
    is_active: bool                         # in corso vs completato

class ExperienceSnapshot(BaseModel):
    """Esperienza lavorativa sintetizzata."""
    company: str | None
    role: str | None
    period: str                             # "2020-2023" o "2023-presente"
    description_summary: str                # max 200 chars
    related_skills: list[str]               # skill estratte da questa esperienza

class RelevantChunk(BaseModel):
    """Chunk testuale recuperato da Qdrant per arricchire il contesto."""
    text: str
    source_collection: Literal["cv_skills", "cv_experiences"]
    similarity_score: float
    section_type: str | None                # skills|experience|education|certifications

class KnowledgeProfile(BaseModel):
    """Profilo completo per il context LLM."""
    cv_id: str
    res_id: int
    full_name: str | None
    current_role: str | None

    # Skill layer — il cuore del profilo
    skills: list[SkillDetail]
    skill_domains: dict[str, int]           # {domain: count} per overview rapida
    total_skills: int
    unknown_skills: list[str]               # skill nel CV non riconosciute dal dizionario

    # Seniority (calcolata, non più "unknown")
    seniority_bucket: Literal["junior", "mid", "senior", "lead", "unknown"]
    years_experience_estimate: int | None

    # Availability layer
    availability: AvailabilityDetail

    # Reskilling layer
    reskilling_paths: list[ReskillingPath]
    has_active_reskilling: bool

    # Experience layer (top experiences rilevanti)
    experiences: list[ExperienceSnapshot]

    # Chunk layer (opzionale, per hybrid context)
    relevant_chunks: list[RelevantChunk]

    # Matching metadata (dal vector search)
    match_score: float                      # score composito dal search
    matched_skills: list[str]               # skill che matchano la query
    missing_skills: list[str]               # skill richieste ma assenti
    match_ratio: float                      # len(matched) / len(query)
```

### 3.3 Come si popola il KP

Il KP non viene costruito per tutti i 10.000 profili. Si costruisce **solo per i candidati pre-filtrati** dal vector search (tipicamente top-7, come da `MAX_DECISION_CANDIDATES`).

```
1. Vector search → top-K ProfileMatch (res_id, cv_id, score, matched/missing)
2. Per ogni candidato:
   a. Redis availability cache → AvailabilityDetail
   b. Redis reskilling cache → ReskillingPath[]  (DA COSTRUIRE)
   c. Qdrant cv_skills payload → SkillDetail[] + metadata
   d. Qdrant cv_experiences payload → ExperienceSnapshot[]
   e. (Opzionale) Qdrant search per chunk rilevanti → RelevantChunk[]
   f. Skill dictionary lookup → related_certifications, domains
   g. Seniority calculator → seniority_bucket  (DA IMPLEMENTARE)
3. Assemblaggio KnowledgeProfile
4. Serializzazione per il context LLM
```

### 3.4 Seniority Bucket: logica di calcolo proposta

Attualmente hardcoded a `"unknown"`. Proposta euristica:

```python
def calculate_seniority(
    years_experience: int | None,
    skills_count: int,
    has_management_skills: bool,
    lead_keywords_in_role: bool,
) -> str:
    if years_experience is None:
        # Fallback su skill count
        if skills_count >= 15 and has_management_skills:
            return "lead"
        if skills_count >= 10:
            return "senior"
        if skills_count >= 5:
            return "mid"
        return "unknown"

    if years_experience >= 12 or (years_experience >= 8 and lead_keywords_in_role):
        return "lead"
    if years_experience >= 6:
        return "senior"
    if years_experience >= 3:
        return "mid"
    if years_experience >= 0:
        return "junior"
    return "unknown"
```

Questa è un'euristica di bootstrap — con il tempo si può trainare un modello più sofisticato sui dati reali.

---

## 4. Le 4 Sorgenti Dati

Il KP si nutre di 4 sorgenti distinte, ognuna con caratteristiche diverse di latenza, formato e affidabilità.

### 4.1 Qdrant — Vettori e Payload

**Collezione `cv_skills`:**
- Un punto per profilo
- Vettore: embedding delle skill canoniche concatenate
- Payload: `cv_id, res_id, normalized_skills[], skill_domain[], seniority_bucket, dictionary_version, created_at`
- Accesso: vector search (query) + payload retrieval (scroll/get)

**Collezione `cv_experiences`:**
- N punti per profilo (uno per esperienza)
- Vettore: embedding della description dell'esperienza
- Payload: `cv_id, res_id, section_type, related_skills[], experience_years, created_at`
- Accesso: filter by res_id + retrieval

**Latenza**: ~10-50ms per query, dipende dal numero di risultati.
**Refresh**: batch, al re-processing del CV.

### 4.2 Skill Dictionary — In-Memory YAML

- Dizionario versionato caricato all'avvio
- Ogni entry: `canonical, domain, aliases[], related[], certifications[]`
- Lookup O(1) per canonical name o alias
- Usato per arricchire le skill con domain, related skills, certifications

**Latenza**: <1ms (in-memory).
**Refresh**: al restart dell'applicazione o reload esplicito.

### 4.3 Redis Availability Cache

- Chiave: `availability:{res_id}`
- Valore: `ProfileAvailability` serializzato
- TTL configurabile
- Accesso: `get(res_id)` o `get_bulk(res_ids)`
- Alimentato dal CSV loader via Celery task periodico

**Latenza**: <5ms.
**Refresh**: periodico via `scraper_availability_csv_refresh_task`.

### 4.4 Redis Reskilling Cache (DA COSTRUIRE)

> **⚠️ AGGIORNAMENTO (Sprint 6):** Il pattern è stato cambiato da CSV loader a consumo via REST API. Vedi §8 per il design aggiornato.

Questa sorgente **non esiste ancora**. Il design proposto consuma dati via REST API dallo scraper service:

- Chiave: `reskilling:{res_id}` → lista di percorsi
- Valore: `list[ReskillingRecord]` serializzato
- TTL: allineato all'availability
- **Sorgente**: REST API `GET /reskilling/csv/{res_id}` → JSON normalizzato
- Service: query per res_id, filtri per skill target, stato attivo/completato

Dettagli nel capitolo 8.

---

## 5. Strategia Hybrid Context: Strutturato + Chunk

Questa è una delle decisioni architetturali più importanti: come comporre il contesto che l'LLM riceve.

### 5.1 Il problema del contesto puro-strutturato

Se alimentiamo l'LLM solo con dati strutturati (skill list, availability status, reskilling paths), perdiamo il **contesto narrativo** del CV: come le skill sono state applicate, in che contesto industriale, con quale tecnologia complementare. Esempio:

```
STRUTTURATO: skills=[Python, FastAPI, PostgreSQL], seniority=senior
```

Questo dice all'LLM "sa Python" ma non che ha "progettato un sistema di microservizi per un operatore telecom gestendo 2M transazioni/giorno con FastAPI e PostgreSQL". La differenza è enorme per una decisione di staffing.

### 5.2 Il problema del contesto puro-chunk

Se passiamo solo chunk di testo dal CV, l'LLM deve inferire le skill, la disponibilità, i percorsi di reskilling — compiti che il nostro pipeline ha già svolto con più precision. L'LLM spreca token e può sbagliare.

### 5.3 La strategia hybrid

La soluzione scelta (confermata dalla decisione "Strutturati + chunk rilevanti") è un approccio a **due livelli**:

**Livello 1 — Dati Strutturati (sempre presenti):**
- Skill list con metadata (domain, confidence, source)
- Availability completa
- Reskilling paths attivi
- Match score e matched/missing skills
- Seniority bucket

**Livello 2 — Chunk Contestuali (on-demand):**
- Top-K chunk da `cv_experiences` pertinenti alla query
- Attivati quando: confidence bassa nel match, skill sconosciute nella query, scenario che richiede valutazione qualitativa (gap analysis, team planning)
- Recuperati via Qdrant search filtrato per `res_id` e query skills

### 5.4 Quando attivare il Livello 2

```python
def should_include_chunks(
    match_score: float,
    unknown_query_skills: list[str],
    scenario: LLMScenario,
) -> bool:
    # Sempre per scenari che richiedono valutazione qualitativa
    if scenario in (LLMScenario.GAP_ANALYSIS, LLMScenario.TEAM_PLANNING):
        return True
    # Se ci sono skill nella query non riconosciute dal dizionario
    if unknown_query_skills:
        return True
    # Se il match score è sotto la soglia di confidenza
    if match_score < 0.65:
        return True
    # Per matching standard con buon score, i dati strutturati bastano
    return False
```

### 5.5 Recupero chunk: strategia

Per ogni candidato che necessita di chunk:

1. Prendi le skill della **query** (non del candidato) come testo di ricerca
2. Cerca in `cv_experiences` filtrato per `res_id = candidato.res_id`
3. Prendi i top-3 chunk per similarity
4. Tronca ogni chunk a ~200 token per rispettare il budget

Questo recupera le esperienze del candidato più pertinenti alla richiesta specifica, non generiche.

---

## 6. Multi-Scenario Prompting

L'integrazione LLM non serve solo il matching JD→CV. Sono stati identificati 5 scenari di uso, ognuno con prompt, contesto e output diversi.

### 6.1 Panoramica scenari

| Scenario | Input | Output | KP Livello |
|----------|-------|--------|------------|
| **Matching** | JD + top-K candidati | Ranking + motivazioni | L1 + L2 opzionale |
| **Reskilling Suggestion** | Profilo IC + skill gap | Piano formativo | L1 + reskilling data |
| **Gap Analysis** | Profilo + ruolo target | Mappa gap + azioni | L1 + L2 |
| **Team Planning** | N posizioni + pool risorse | Composizione team | L1 per tutti |
| **Reportistica** | Pool risorse + filtri | Analisi aggregata | L1 aggregato |

### 6.2 Scenario 1: Matching (JD → Candidato)

Il caso d'uso principale. Una JD con skill richieste, il sistema trova e ranking i migliori candidati.

**Flow:**
```
JD text → skill extraction → vector search → top-7 candidati →
  → KP assembly per ognuno → LLM prompt → DecisionOutput
```

**Prompt structure:**
```
SYSTEM: Sei un esperto di staffing IT. Il tuo compito è analizzare i candidati
        e selezionare il migliore per la posizione richiesta.
        Principio: skill = segnale primario, esperienza = supporto,
        disponibilità = vincolo.

CONTEXT: [KP serializzati dei 7 candidati]

USER: Posizione richiesta: {jd_title}
      Skill richieste: {jd_skills}
      Skill preferite: {jd_preferred_skills}
      Disponibilità richiesta: {start_date} - {end_date}
      Alloca il miglior candidato.

OUTPUT FORMAT: JSON con selected_cv_id, decision_reason, matched_skills,
              missing_skills, confidence, alternatives[]
```

**Decision logic che l'LLM deve seguire:**
1. Filtra candidati non disponibili nel periodo richiesto
2. Ranking per copertura skill richieste (match_ratio)
3. A parità di copertura, preferisci chi ha confidence più alta nelle skill
4. Considera skill in reskilling come copertura parziale (peso ~0.5)
5. Se nessun candidato copre >70% delle skill, segnala confidence "low"

### 6.3 Scenario 2: Reskilling Suggestion

Data una risorsa IC, suggerire un percorso di reskilling basato sulle skill gap rispetto ai ruoli più richiesti dal mercato/portafoglio progetti.

**Flow:**
```
Profilo IC → KP assembly → analisi skill possedute →
  → confronto con skill demand (da JD storiche o configurazione) →
  → LLM prompt → ReskillingPlan
```

**Prompt structure:**
```
SYSTEM: Sei un career advisor IT. Analizza il profilo della risorsa
        e suggerisci un percorso di reskilling realistico.

CONTEXT: [KP della risorsa]
         [Top skill richieste negli ultimi 3 mesi]
         [Reskilling paths già attivi]

USER: Questa risorsa è in intercontratto ({ic_sub_state}).
      Suggerisci un piano di reskilling di max {months} mesi
      per massimizzare la sua occupabilità.

OUTPUT FORMAT: JSON con target_role, skill_gaps[], recommended_courses[],
              estimated_timeline, priority, rationale
```

### 6.4 Scenario 3: Gap Analysis

Dato un profilo e un ruolo target, analizzare i gap e proporre azioni concrete.

**Flow:**
```
Profilo + Ruolo target → KP assembly + chunk rilevanti →
  → skill confronto (possedute vs richieste) →
  → LLM prompt → GapAnalysis
```

**Output schema:**
```python
class GapAnalysis(BaseModel):
    profile_cv_id: str
    target_role: str
    covered_skills: list[str]           # skill possedute che matchano
    partial_skills: list[str]           # skill in reskilling o con bassa confidence
    missing_skills: list[str]           # skill completamente assenti
    coverage_pct: float                 # % copertura
    recommended_actions: list[str]      # azioni concrete
    estimated_readiness_months: int     # mesi stimati per essere ready
    confidence: Literal["high", "medium", "low"]
```

### 6.5 Scenario 4: Team Planning

Data una richiesta multi-posizione, comporre un team ottimale dal pool disponibile. Questo è lo scenario più complesso.

**Flow:**
```
N posizioni con skill requirements → pool risorse disponibili →
  → KP assembly per il pool → LLM prompt → TeamComposition
```

**Complessità specifica:**
- L'LLM deve ragionare su **complementarità**: non 3 backend senior identici, ma un mix di seniority e specializzazioni
- Deve considerare **vincoli di disponibilità temporale**: le risorse devono essere disponibili nello stesso periodo
- Deve valutare **reskilling in corso**: una risorsa IC che sta completando un corso rilevante potrebbe essere pianificata per una fase successiva del progetto

**Output schema:**
```python
class TeamComposition(BaseModel):
    positions: list[PositionAssignment]
    unassigned_positions: list[str]     # posizioni senza candidato adatto
    team_coverage_pct: float            # copertura complessiva
    team_risk_assessment: str           # valutazione rischi
    rationale: str

class PositionAssignment(BaseModel):
    position_title: str
    assigned_cv_id: str
    match_score: float
    key_strengths: list[str]
    gaps: list[str]
    availability_note: str              # "disponibile da subito" / "disponibile dal ..."
```

### 6.6 Scenario 5: Reportistica Intelligente

Generare report aggregati sul pool risorse con insight: distribuzione skill, concentrazione IC, trend reskilling, capacity planning.

**Flow:**
```
Pool risorse (filtro opzionale) → aggregazione dati →
  → LLM prompt → Report narrativo + dati
```

Questo scenario è diverso dagli altri: l'LLM non riceve KP individuali ma **dati aggregati**:
- Distribuzione skill per dominio
- Conteggio per availability status
- Risorse IC per sotto-stato
- Percorsi reskilling attivi per skill target
- Trend temporali (se disponibili)

**L'LLM produce narrativa**, non decisioni puntuali. Serve temperature più alta (~0.3 vs 0.1 del matching) per generare testo più fluido.

---

## 7. IC (Intercontratto) e Sotto-Stati

L'IC è una risorsa con `allocation_pct == 0` — è "on bench". Ma non tutti gli IC sono uguali.

### 7.1 Definizione sotto-stati

| Sotto-stato | Condizione | Significato |
|------------|------------|-------------|
| `ic_available` | IC + nessun reskilling attivo + nessun colloquio in corso | Disponibile immediatamente per staffing |
| `ic_in_reskilling` | IC + almeno un reskilling path attivo | In formazione, disponibile con vincoli |
| `ic_in_transition` | IC + flag transizione (colloquio/proposta in corso) | Potenzialmente non disponibile a breve |

### 7.2 Calcolo del sotto-stato

```python
def determine_ic_sub_state(
    availability: ProfileAvailability,
    reskilling_paths: list[ReskillingPath],
    is_in_transition: bool = False,  # flag esterno, da HR/manager
) -> str | None:
    # Non è IC
    if availability.allocation_pct > 0:
        return None
    if availability.status not in (AvailabilityStatus.FREE, AvailabilityStatus.UNAVAILABLE):
        return None

    # Priorità: transizione > reskilling > available
    if is_in_transition:
        return "ic_in_transition"

    active_reskilling = [r for r in reskilling_paths if r.is_active]
    if active_reskilling:
        return "ic_in_reskilling"

    return "ic_available"
```

### 7.3 Impatto sulle decisioni LLM

Il sotto-stato IC influenza direttamente le decisioni:

- **ic_available**: candidato ideale per staffing immediato, da considerare come "free" con priorità (ridurre il bench è un obiettivo aziendale)
- **ic_in_reskilling**: candidato con potenziale futuro; se il reskilling copre skill richieste e è a buon punto (>60% completamento), l'LLM può suggerirlo per una fase successiva del progetto
- **ic_in_transition**: da escludere o segnalare come rischioso (potrebbe non essere disponibile)

Nel prompt di matching, il system prompt deve includere:

> "Le risorse IC-available hanno priorità: a parità di match score, preferisci una risorsa IC
> per ridurre il bench. Le risorse IC-in-reskilling possono essere considerate se il percorso
> formativo è pertinente alla posizione e la data di fine corso è compatibile."

---

## 8. Reskilling: Infrastruttura Mancante e Design

### 8.1 Stato attuale

L'infrastruttura reskilling in ProfileBot è a quota zero:

| Componente | Availability | Reskilling |
|-----------|-------------|-----------|
| Schema Pydantic | `ProfileAvailability` | **MANCANTE** |
| Format guide / Contratto | `availability_format_guide.md` | `scraper-service-openapi.yaml` (REST) |
| Loader / Normalizer | `availability/loader.py` (CSV) | **normalizer.py (JSON row → Pydantic)** |
| Cache (Redis) | `availability/cache.py` | **MANCANTE** |
| Service | `availability/service.py` | **MANCANTE** |
| Celery task | `scraper_availability_csv_refresh_task` | `scraper_reskilling_csv_refresh_task` (solo trigger) |
| Scraper endpoint | `/availability/csv` | `/reskilling/csv` (esiste) |

### 8.2 REST API Reskilling (pattern aggiornato)

> **⚠️ AGGIORNAMENTO (Sprint 6):** Il pattern è stato cambiato da CSV canonico a consumo via REST API. Il contratto tecnico è definito in `docs/scraper-service/scraper-service-openapi.yaml`.

Lo scraper service espone l'endpoint `GET /reskilling/csv/{res_id}` che restituisce un `RowResponse` JSON:

```json
{
  "res_id": "210513",
  "row": {
    "Risorsa:Consultant ID": "210513",
    "Risorsa": "Donnemma, Debora",
    // ... altri campi dinamici dal SharePoint
  }
}
```

Il campo `row` ha `additionalProperties: true` — i nomi dei campi vengono dal tracciato SharePoint e vanno **mappati/normalizzati** nel nostro schema Pydantic tramite un `normalizer.py`.

**Mapping campi SharePoint → ReskillingRecord:**

| Campo SharePoint (raw) | Campo Pydantic | Tipo | Obbligatorio |
|------------------------|---------------|------|:---:|
| `Risorsa:Consultant ID` | `res_id` | int | Si |
| (da definire in fase di implementazione) | `course_name` | string | Si |
| (da definire) | `target_skills` | list[str] | Si |
| (da definire) | `completion_pct` | int | Si |
| (da definire) | `start_date` | date | No |
| (da definire) | `end_date` | date | No |
| (da definire) | `status` | ReskillingStatus | Si |
| (da definire) | `updated_at` | datetime | Si |

> **Nota:** Il mapping esatto dei nomi di campo SharePoint verrà definito in fase di implementazione US-009.2, analizzando le risposte reali dell'endpoint.

### 8.3 Schema Pydantic

```python
class ReskillingStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"

class ReskillingRecord(BaseModel):
    res_id: int
    course_name: str
    target_skills: list[str]        # skill canoniche
    completion_pct: int = Field(ge=0, le=100)
    provider: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: ReskillingStatus
    updated_at: datetime
```

### 8.4 Implementazione proposta (aggiornata Sprint 6)

Seguire il pattern REST API (diverso dall'availability che usa CSV loader):

1. **`src/services/reskilling/schemas.py`** → `ReskillingRecord`, `ReskillingStatus`
2. **`src/services/reskilling/normalizer.py`** → mapping JSON row SharePoint → `ReskillingRecord` Pydantic
3. **`src/services/reskilling/cache.py`** → `ReskillingCache` (Redis, chiave `reskilling:{res_id}`, valore `list[ReskillingRecord]` serializzato JSON)
4. **`src/services/reskilling/service.py`** → `ReskillingService` (get_by_res_id, get_active_by_res_id, get_bulk, filter_by_target_skill)
5. **`src/services/scraper/client.py`** → aggiungere `fetch_reskilling_row(res_id)` per consumo `GET /reskilling/csv/{res_id}`
6. **`src/services/reskilling/tasks.py`** → Celery task `reskilling_refresh_task` che itera sui res_id, chiama REST API, normalizza e cacha

### 8.5 Integrazione nel KP

Una volta costruita l'infrastruttura reskilling, il KP builder potrà:

```python
async def build_kp(res_id: int, ...) -> KnowledgeProfile:
    # ... altri dati ...
    reskilling_records = reskilling_service.get_by_res_id(res_id)
    reskilling_paths = [
        ReskillingPath(
            course_name=r.course_name,
            target_skills=r.target_skills,
            completion_pct=r.completion_pct,
            provider=r.provider,
            start_date=r.start_date,
            end_date=r.end_date,
            is_active=(r.status == ReskillingStatus.ACTIVE),
        )
        for r in reskilling_records
    ]
    # Le skill dal reskilling completato diventano SkillDetail con source="reskilling"
    for record in reskilling_records:
        if record.status == ReskillingStatus.COMPLETED:
            for skill_name in record.target_skills:
                skills.append(SkillDetail(
                    canonical=skill_name,
                    domain=dictionary.get_domain(skill_name),
                    confidence=0.7,  # confidence ridotta rispetto a CV
                    match_type="exact",
                    source="reskilling",
                    reskilling_completion_pct=100,
                    ...
                ))
```

---

## 9. Architettura del Context Builder

Il Context Builder è il componente che trasforma i KP in testo per il prompt LLM. La sua qualità determina direttamente la qualità delle decisioni.

### 9.1 Principi di serializzazione

1. **Struttura chiara**: sezioni delimitate per ogni candidato, con header visivi
2. **Informazione gerarchica**: skill prima, poi availability, poi reskilling, poi esperienze, poi chunk
3. **Densità controllata**: nessuna verbosità inutile, ogni token deve portare informazione
4. **Differenziazione**: evidenziare ciò che distingue un candidato dagli altri (matched vs missing skills)

### 9.2 Template di serializzazione KP

```
═══ CANDIDATO {n}/{total} ═══
ID: {cv_id} | Res: {res_id}
Nome: {full_name} | Ruolo: {current_role}
Seniority: {seniority_bucket} | Anni esperienza: {years}
Match Score: {score:.2f} | Copertura: {match_ratio:.0%}

▸ SKILL MATCHATE ({count}): {matched_skills_comma_separated}
▸ SKILL MANCANTI ({count}): {missing_skills_comma_separated}
▸ TUTTE LE SKILL ({total}):
  [backend] Python (cv, 0.95), FastAPI (cv, 0.90), Django (reskilling, 70%)
  [data] PostgreSQL (cv, 0.85), Redis (cv, 0.80)
  [devops] Docker (cv, 0.75), Kubernetes (reskilling, 40%)

▸ DISPONIBILITÀ: {status} | Allocazione: {allocation_pct}%
  Progetto: {current_project}
  Disponibile: {available_from} → {available_to}
  Manager: {manager_name}
  IC: {is_intercontratto} ({ic_sub_state})

▸ RESKILLING ATTIVO:
  - Kubernetes Fundamentals (75%, CloudAcademy, scade 2026-03-15)
    Target: kubernetes, docker, helm

▸ ESPERIENZE RILEVANTI:
  1. [2020-2023] Backend Developer @ Acme Corp
     "Sviluppo microservizi Python per piattaforma e-commerce"
     Skills: Python, FastAPI, PostgreSQL, Docker

  2. [2023-oggi] Senior Developer @ TechCo
     "Architettura event-driven per sistema IoT"
     Skills: Python, Kafka, Kubernetes, AWS

▸ CHUNK CONTESTUALI (se presenti):
  [similarity: 0.87] "Ha progettato e implementato un sistema di processing
   real-time basato su Kafka gestendo 500k eventi/giorno con latenza <100ms..."
═══════════════════════════
```

### 9.3 Implementazione del Context Builder

```python
class KPContextBuilder:
    """Trasforma KnowledgeProfile in testo per il prompt LLM."""

    def __init__(
        self,
        max_skills_per_domain: int = 10,
        max_experiences: int = 3,
        max_chunks: int = 3,
        max_chunk_chars: int = 300,
    ) -> None:
        self._max_skills_per_domain = max_skills_per_domain
        self._max_experiences = max_experiences
        self._max_chunks = max_chunks
        self._max_chunk_chars = max_chunk_chars

    def build(
        self,
        profiles: list[KnowledgeProfile],
        scenario: LLMScenario,
    ) -> str:
        """Serializza i KP in contesto testuale."""
        sections = []
        for i, kp in enumerate(profiles, 1):
            sections.append(self._serialize_kp(kp, index=i, total=len(profiles), scenario=scenario))
        return "\n\n".join(sections)

    def _serialize_kp(self, kp: KnowledgeProfile, *, index: int, total: int, scenario: LLMScenario) -> str:
        lines = [f"═══ CANDIDATO {index}/{total} ═══"]
        lines.append(f"ID: {kp.cv_id} | Res: {kp.res_id}")
        # ... header, skills, availability, reskilling, experiences, chunks ...
        # La logica di troncamento e selezione dipende dallo scenario
        if scenario == LLMScenario.MATCHING:
            # Focus su matched/missing skills e availability
            ...
        elif scenario == LLMScenario.RESKILLING_SUGGESTION:
            # Focus su skill possedute, gap, e reskilling in corso
            ...
        lines.append("═══════════════════════════")
        return "\n".join(lines)

    def estimate_tokens(self, text: str) -> int:
        """Stima approssimativa dei token (1 token ≈ 4 chars per testo misto)."""
        return len(text) // 4
```

---

## 10. Token Budget e Ottimizzazione

### 10.1 Vincoli

| Modello | Context Window | Output Max | Costo/1K input | Costo/1K output |
|---------|:-:|:-:|:-:|:-:|
| GPT-4o | 128K | 16K | $0.0025 | $0.01 |
| GPT-4o-mini | 128K | 16K | $0.00015 | $0.0006 |
| Ollama (locale) | 8-32K | 4-8K | $0 | $0 |

**Budget target per richiesta di matching:**
- System prompt: ~500 token
- Contesto (7 candidati): ~3500-7000 token (500-1000 per candidato)
- User prompt: ~200 token
- Output: ~500-1000 token
- **Totale**: ~5000-9000 token

Questo è compatibile con tutti i modelli, incluso Ollama con context window di 8K (se si limita a 3-5 candidati).

### 10.2 Strategia di riduzione token

Se il budget viene superato:

1. **Ridurre candidati**: da MAX_DECISION_CANDIDATES (7) a 5 o 3
2. **Rimuovere chunk**: primo livello da tagliare
3. **Troncare esperienze**: da 3 a 1 per candidato
4. **Comprimere skill list**: solo matched + missing, non tutte
5. **Rimuovere reskilling completati**: mantenere solo attivi

```python
def fit_budget(
    profiles: list[KnowledgeProfile],
    max_tokens: int,
    builder: KPContextBuilder,
) -> list[KnowledgeProfile]:
    """Riduce progressivamente il contesto per rispettare il budget."""
    text = builder.build(profiles, scenario)
    if builder.estimate_tokens(text) <= max_tokens:
        return profiles

    # Step 1: rimuovi chunk
    for kp in profiles:
        kp.relevant_chunks = []
    text = builder.build(profiles, scenario)
    if builder.estimate_tokens(text) <= max_tokens:
        return profiles

    # Step 2: riduci esperienze
    for kp in profiles:
        kp.experiences = kp.experiences[:1]
    # ...

    # Step 3: riduci candidati
    return profiles[:max_tokens // 1000]  # euristica
```

### 10.3 Caching semantico

Per query ricorrenti (es. stesse skill richieste), si può implementare un **semantic cache**:

- Chiave: hash dell'embedding della query + hash dei res_id candidati
- Valore: DecisionOutput
- TTL: breve (1h) perché la disponibilità cambia
- Storage: Redis

Questo riduce drasticamente i costi per query ripetute (es. refresh della stessa ricerca).

---

## 11. Prompt Engineering per Scenario

### 11.1 System Prompt — Struttura base

Ogni scenario condivide una base comune ma con istruzioni specifiche:

```python
SYSTEM_PROMPT_BASE = """Sei un assistente AI specializzato in staffing IT e gestione risorse.

PRINCIPI FONDAMENTALI:
1. Skills = segnale decisionale primario
2. Esperienze = supporto e validazione delle skill
3. Disponibilità = vincolo (non suggerire risorse non disponibili)
4. Reskilling = potenziale futuro (peso inferiore a skill confermate)

REGOLE:
- Rispondi SEMPRE in formato JSON valido
- Motiva ogni decisione con riferimenti specifici ai dati del candidato
- Se non hai informazioni sufficienti, indica confidence "low"
- Non inventare dati: usa solo ciò che è nel contesto
- Le risorse IC-available hanno priorità a parità di match score
"""

SCENARIO_PROMPTS = {
    LLMScenario.MATCHING: SYSTEM_PROMPT_BASE + """
SCENARIO: Matching JD → Candidato
Devi selezionare il candidato migliore per la posizione richiesta.
Considera: copertura skill (>70% = buona), seniority adeguata,
disponibilità nel periodo, reskilling pertinente.
""",

    LLMScenario.RESKILLING_SUGGESTION: SYSTEM_PROMPT_BASE + """
SCENARIO: Suggerimento Reskilling
Devi proporre un piano formativo realistico per una risorsa IC.
Considera: skill attuali, gap rispetto al mercato, percorsi già attivi,
tempistiche realistiche (max 3-6 mesi per skill tecnica).
""",

    LLMScenario.GAP_ANALYSIS: SYSTEM_PROMPT_BASE + """
SCENARIO: Gap Analysis
Devi analizzare il divario tra le skill di un profilo e un ruolo target.
Categorizza: skill coperte, parziali (in reskilling), mancanti.
Proponi azioni concrete per ogni gap.
""",

    LLMScenario.TEAM_PLANNING: SYSTEM_PROMPT_BASE + """
SCENARIO: Pianificazione Team
Devi comporre un team ottimale da un pool di risorse.
Considera: complementarità skill, mix seniority, disponibilità
contemporanea, risorse IC da valorizzare.
""",

    LLMScenario.REPORTING: SYSTEM_PROMPT_BASE + """
SCENARIO: Reportistica
Devi generare un'analisi narrativa dei dati aggregati.
Focus: insight actionable, trend significativi, raccomandazioni.
Tono: professionale ma accessibile, adatto a management.
""",
}
```

### 11.2 Output Schema per scenario

Ogni scenario ha un output schema Pydantic dedicato. L'LLM riceve istruzioni esplicite sul formato JSON atteso:

```python
class MatchingOutput(DecisionOutput):
    """Output per scenario Matching."""
    selected_cv_id: str
    decision_reason: str
    matched_skills: list[str]
    missing_skills: list[str]
    confidence: Literal["high", "medium", "low"]
    alternatives: list[AlternativeCandidate]

class ReskillingPlanOutput(BaseModel):
    """Output per scenario Reskilling Suggestion."""
    target_role: str
    skill_gaps: list[SkillGap]
    recommended_courses: list[CourseRecommendation]
    estimated_timeline_months: int
    priority: Literal["high", "medium", "low"]
    rationale: str

class GapAnalysisOutput(BaseModel):
    """Output per scenario Gap Analysis."""
    profile_cv_id: str
    target_role: str
    covered_skills: list[str]
    partial_skills: list[PartialSkill]
    missing_skills: list[str]
    coverage_pct: float
    recommended_actions: list[str]
    estimated_readiness_months: int
    confidence: Literal["high", "medium", "low"]

class TeamCompositionOutput(BaseModel):
    """Output per scenario Team Planning."""
    assignments: list[PositionAssignment]
    unassigned_positions: list[str]
    team_coverage_pct: float
    risk_assessment: str
    rationale: str

class ReportOutput(BaseModel):
    """Output per scenario Reportistica."""
    summary: str
    key_insights: list[str]
    recommendations: list[str]
    data_highlights: dict[str, Any]
```

### 11.3 Parsing e validazione output

```python
def parse_llm_output(
    raw_content: str,
    scenario: LLMScenario,
) -> BaseModel:
    """Parse e valida l'output LLM secondo lo scenario."""
    output_schemas = {
        LLMScenario.MATCHING: MatchingOutput,
        LLMScenario.RESKILLING_SUGGESTION: ReskillingPlanOutput,
        LLMScenario.GAP_ANALYSIS: GapAnalysisOutput,
        LLMScenario.TEAM_PLANNING: TeamCompositionOutput,
        LLMScenario.REPORTING: ReportOutput,
    }

    schema = output_schemas[scenario]

    # Estrai JSON dal testo (l'LLM potrebbe wrappare in ```json```)
    json_str = extract_json_from_text(raw_content)
    data = json.loads(json_str)
    return schema.model_validate(data)
```

---

## 12. Gap Analysis del Codebase Attuale

Riassunto dei gap identificati nell'analisi del codice, ordinati per priorità.

### 12.1 Gap Critici (bloccanti per il KP)

| # | Gap | File/Area | Impatto | Effort |
|:-:|-----|-----------|---------|:------:|
| 1 | **Reskilling infrastructure assente** | `src/services/reskilling/` | Nessun dato reskilling nel KP | L |
| 2 | **Seniority bucket sempre "unknown"** | `embedding/pipeline.py` L149 | KP senza seniority | S |
| 3 | **DecisionCandidate troppo scarno** | `llm/schemas.py` | L'LLM non ha contesto sufficiente | M |
| 4 | **Config.py senza campi LLM** | `core/config.py` | LLM client non configurabile | S |

### 12.2 Gap Importanti (limitano la qualità)

| # | Gap | File/Area | Impatto | Effort |
|:-:|-----|-----------|---------|:------:|
| 5 | **Context builder piatto** | `llm/prompts.py` | Contesto non strutturato per l'LLM | M |
| 6 | **Nessun scenario enum** | `llm/` | Solo matching, no multi-scenario | M |
| 7 | **Nessun KP builder** | — | Assemblaggio KP manuale | M |
| 8 | **Chunk retrieval assente** | — | No hybrid context | M |

### 12.3 Gap Minori (miglioramenti)

| # | Gap | File/Area | Impatto | Effort |
|:-:|-----|-----------|---------|:------:|
| 9 | **Nessun semantic cache** | — | Costi LLM non ottimizzati | S |
| 10 | **Nessun token budget management** | — | Rischio context overflow | S |
| 11 | **last_used_hint non calcolato** | — | Skill recency sconosciuta | S |
| 12 | **IC sub-state non calcolato** | — | IC trattati tutti uguali | S |

S = Small (1-2 giorni), M = Medium (3-5 giorni), L = Large (5-10 giorni)

---

## 13. Roadmap Implementativa

### Fase 1: Fondamenta (Sprint 4-5)

**Obiettivo**: costruire l'infrastruttura dati mancante e il KP model base.

| Task | US | Dipendenza | Effort |
|------|:--:|:----------:|:------:|
| Config.py: aggiungere campi LLM | US-009 | — | S |
| Seniority calculator | — | — | S |
| Reskilling schemas + normalizer | — | — | S |
| Reskilling cache + service (REST) | — | schemas | M |
| Reskilling Celery task integration | — | service | S |
| KnowledgeProfile schema | — | reskilling schemas | S |
| IC sub-state calculator | — | reskilling service | S |

### Fase 2: KP Builder e Context (Sprint 5-6)

**Obiettivo**: assemblare il KP e creare il context builder evoluto.

| Task | Dipendenza | Effort |
|------|:----------:|:------:|
| KP Builder service (assembla da 4 sorgenti) | Fase 1 completa | M |
| LLMScenario enum | — | S |
| KPContextBuilder (serializzazione KP → testo) | KP Builder | M |
| Token budget manager | Context Builder | S |
| Chunk retrieval per hybrid context | Context Builder | M |

### Fase 3: Multi-Scenario Prompting (Sprint 6-7)

**Obiettivo**: implementare i 5 scenari con prompt e output schema dedicati.

| Task | Dipendenza | Effort |
|------|:----------:|:------:|
| Scenario Matching (evoluzione US-009) | Fase 2 | M |
| Scenario Gap Analysis | Fase 2 | M |
| Scenario Reskilling Suggestion | Fase 2 + reskilling infra | M |
| Scenario Team Planning | Fase 2 | L |
| Scenario Reporting | Fase 2 | M |
| Output parsing + validation per scenario | Tutti gli scenari | S |

### Fase 4: Ottimizzazione (Sprint 7-8)

| Task | Dipendenza | Effort |
|------|:----------:|:------:|
| Semantic cache (Redis) | Fase 3 | S |
| Performance benchmarking | Fase 3 | M |
| Prompt tuning con dati reali | Fase 3 | M |
| Ollama testing e ottimizzazione | — | M |

### Diagramma dipendenze

```
[Config LLM] ──────────────────────────────┐
[Seniority Calc] ────────────────────┐      │
[Reskilling Infra] ──→ [IC Sub-State]│      │
                            │        │      │
                            ▼        ▼      ▼
                    [KP Schema] ──→ [KP Builder]
                                        │
                                        ▼
                                 [Context Builder] ──→ [Token Budget]
                                        │
                                        ▼
                              [Scenario Matching] ──→ [Semantic Cache]
                              [Scenario Gap Analysis]
                              [Scenario Reskilling]
                              [Scenario Team Planning]
                              [Scenario Reporting]
```

---

## 14. Antipattern e Rischi

### 14.1 Antipattern da evitare

**AP-1: LLM come classificatore skill**
> Non usare l'LLM per normalizzare o classificare skill. Il dizionario + normalizer lo fanno meglio, più veloce, più deterministico. L'LLM serve per la decisione finale.

**AP-2: Contesto dump**
> Non passare all'LLM tutto il raw text del CV. Il vector search e lo skill extraction hanno già fatto il lavoro pesante. Il contesto deve essere curato e strutturato.

**AP-3: Prompt generico per tutti gli scenari**
> Ogni scenario ha esigenze diverse. Un prompt di matching non funziona per il reskilling. Investire in prompt specifici per scenario.

**AP-4: Ignorare i token**
> Non assumere che il context window sia infinito. Con Ollama a 8K, 7 candidati con chunk non ci stanno. Il token budget manager è essenziale.

**AP-5: Fidarsi ciecamente dell'output LLM**
> L'LLM può allucinare. Validare sempre l'output con Pydantic e verificare che i cv_id nell'output esistano nei candidati input. Non accettare skill inventate.

**AP-6: Cache senza invalidazione**
> Il semantic cache è utile ma pericoloso se la disponibilità cambia. TTL breve (1h) e invalidazione esplicita quando l'availability cache si aggiorna.

### 14.2 Rischi e mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|:-:|:-:|-------------|
| Output LLM non parsabile | Media | Alto | Retry con temperatura ridotta, fallback su regex parsing |
| Latenza alta (>5s per decisione) | Media | Medio | Parallelizzare KP assembly, caching, modello più piccolo |
| Costi LLM elevati con GPT-4o | Bassa | Medio | Semantic cache, routing su GPT-4o-mini per scenari semplici |
| Ollama qualità insufficiente | Media | Alto | Benchmark comparativo, fallback su API cloud |
| Reskilling data non disponibile | Alta (oggi) | Medio | Graceful degradation: KP senza reskilling funziona comunque |
| IC sub-state errato | Bassa | Basso | Flag manuale da HR come override |

---

## 15. Appendice: Schema Dati Completo

### 15.1 Enum e tipi base

```python
from enum import StrEnum
from typing import Literal

class LLMScenario(StrEnum):
    MATCHING = "matching"
    RESKILLING_SUGGESTION = "reskilling_suggestion"
    GAP_ANALYSIS = "gap_analysis"
    TEAM_PLANNING = "team_planning"
    REPORTING = "reporting"

class AvailabilityStatus(StrEnum):
    FREE = "free"
    PARTIAL = "partial"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"

class ReskillingStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"

SeniorityBucket = Literal["junior", "mid", "senior", "lead", "unknown"]
ICSubState = Literal["ic_available", "ic_in_reskilling", "ic_in_transition", None]
SkillSource = Literal["cv", "reskilling"]
MatchType = Literal["exact", "alias", "fuzzy"]
ConfidenceLevel = Literal["high", "medium", "low"]
```

### 15.2 Flusso dati end-to-end

```
                    ┌──────────────┐
                    │   JD / Query │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Skill Extract │
                    │ + Normalize   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Vector Search │ ─── Qdrant (cv_skills)
                    │ + Scoring     │
                    └──────┬───────┘
                           │
                    top-K ProfileMatch
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼───┐ ┌──────▼──────┐
       │  Availability│ │Qdrant│ │  Reskilling  │
       │  (Redis)     │ │Payload│ │  (Redis)     │
       └──────┬──────┘ └──┬───┘ └──────┬──────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼───────┐
                    │  KP Builder   │ ←── Skill Dictionary
                    └──────┬───────┘
                           │
                   list[KnowledgeProfile]
                           │
                    ┌──────▼───────┐
                    │Context Builder│ ←── Scenario, Token Budget
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  LLM Client   │ ←── OpenAI / Azure / Ollama
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Output Parse  │
                    │ + Validation  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Decision     │
                    │  Output       │
                    └──────────────┘
```

### 15.3 Configurazione .env (target)

```env
# LLM Provider Configuration
LLM_PROVIDER=openai                     # openai | azure | ollama
LLM_MODEL=gpt-4o-mini                  # nome modello
LLM_BASE_URL=                          # vuoto per OpenAI default, URL per Ollama/Azure
LLM_API_KEY=sk-...                     # API key (o "ollama" per Ollama)
LLM_TEMPERATURE=0.1                    # default per matching
LLM_MAX_TOKENS=2000                    # max output tokens
LLM_MAX_CONTEXT_TOKENS=8000            # budget per il contesto

# Scenario-specific overrides (opzionale)
LLM_REPORTING_TEMPERATURE=0.3          # temperatura più alta per reportistica
LLM_TEAM_PLANNING_MAX_TOKENS=4000      # output più lungo per team planning
```

---

> **Questo documento è un living document.** Va aggiornato man mano che l'implementazione procede
> e le decisioni architetturali si consolidano. Ogni cambiamento significativo va tracciato
> con un ADR dedicato nella cartella `docs/adr/`.
