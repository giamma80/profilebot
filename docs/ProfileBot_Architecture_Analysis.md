# ProfileBot — Architettura del Data Aggregation Pipeline

**Analisi AS-IS, Gap Analysis e Proposta Evolutiva**

Skill-First Search | Experience-Enriched Ranking | Reskilling Prediction

Versione 1.0 | Marzo 2026

---

## 1. Executive Summary

ProfileBot aggrega dati professionali da fonti eterogenee (CV DOCX, availability CSV, reskilling CSV) per costruire un motore di ricerca semantico di profili. L'architettura attuale funziona ma presenta **limiti strutturali** nella capacità di sfruttare appieno le dimensioni del dato raccolto.

Questo documento analizza lo stato corrente (AS-IS) della pipeline di aggregazione dati, identifica i gap rispetto a un modello di ricerca **skill-first** con ranking arricchito dalle esperienze, e propone un'architettura evolutiva (TO-BE) che include:

| Area | Descrizione |
|---|---|
| **Ricerca Skill-First** | Priorità sulle competenze, non sul testo grezzo del CV |
| **Ranking Experience-Enriched** | Le esperienze rafforzano e specializzano lo score |
| **Reskilling Predittivo** | Proiezione del percorso di crescita del profilo |
| **Profile Statistics API** | Endpoint dedicato per valutazione e statistiche del profilo |
| **Workflow Resiliente** | Pipeline tollerante ai fallimenti parziali |

---

## 2. Architettura AS-IS

### 2.1 Data Sources

ProfileBot ingesta dati da tre fonti distinte, ciascuna gestita dal legacy scraper service:

| Fonte | Formato | Contenuto | Frequenza |
|---|---|---|---|
| CV Inside | DOCX | CV completo: skill, esperienze, education, certificazioni | Ogni 4h (cron) |
| Availability CSV | CSV | Stato disponibilità: FREE, PARTIAL, BUSY, UNAVAILABLE | Ogni 4h (cron) |
| Reskilling CSV | CSV | Processi in corso: tipo formazione, skill target | Ogni 4h (cron) |

### 2.2 Ingestion Pipeline

Il workflow di ingestion è orchestrato da **Celery** tramite un DAG definito in `res_id_workflow.yaml`. La sequenza operativa è:

1. **fetch_res_ids** → Recupera la lista di res_id attivi dal scraper
2. **inside_fanout** → Per ogni res_id: refresh + download CV, parse DOCX, extract skills via LLM
3. **export_availability** + **export_reskilling** → Trigger export CSV parallelo
4. **embed_all** → Genera embedding per skills + experiences, upsert su Qdrant

> **⚠ DIFETTO CRITICO IDENTIFICATO (Issue #65 — P0-critical):**
> Il task `scraper.inside_refresh` (step 1) attualmente NON si limita a recuperare i res_id: contiene un loop sincrono che processa TUTTI i profili in sequenza (chiamando `refresh_inside_cv` per ognuno). Questo causa:
> - **(a)** timeout dopo ~500s con retry dall'inizio, perdendo tutto il lavoro;
> - **(b)** doppia elaborazione, perché lo step 2 (`inside_fanout`) ricrea gli stessi task individuali.
>
> La soluzione approvata prevede che `fetch_res_ids` faccia SOLO fetch + cache dei res_id, delegando tutto il processing al fanout (vedi [sezione 4.5.2](#452-pattern-fetchrefresh-decoupling-issue-65--p0-critical)).

### 2.3 Modello Dati: NormalizedDocument

Il modello centrale dell'ingestion è `NormalizedDocument` che struttura il CV in sezioni:

| Campo | Tipo | Descrizione |
|---|---|---|
| `cv_id` | UUID | Identificativo univoco del documento |
| `res_id` | int | Identificativo della risorsa nel sistema legacy |
| `source_type` | Enum | `DOCX_CV` \| `AVAILABILITY_CSV` \| `RESKILLING_API` |
| `sections` | Dict | Mappa sezione → contenuto (skills, experience, education, certifications) |
| `metadata` | Dict | Metadati estratti: nome, ruolo, seniority, lingue |
| `raw_text` | str | Testo completo del CV per fallback |

### 2.4 Embedding & Qdrant Collections

L'EmbeddingPipeline produce punti vettoriali su **due collection Qdrant** separate:

| Collection | Granularità | Payload Indexes | Utilizzo |
|---|---|---|---|
| `cv_skills` | 1 punto per CV | cv_id, res_id, normalized_skills, skill_domain, seniority_bucket | Ricerca skill-based primaria |
| `cv_experiences` | N punti per CV | cv_id, res_id, related_skills, experience_years | Ricerca per esperienza specifica |

Gli ID sono **deterministici** (UUID5 basato su cv_id + suffisso), garantendo idempotenza negli upsert. Il modello di embedding è configurabile (default: `text-embedding-ada-002` via OpenAI).

### 2.5 Search Layer

L'endpoint **POST /api/v1/search/skills** implementa il flusso:

1. **Normalize** → Normalizza skill della query tramite SkillNormalizer (dizionario canonico)
2. **Embed** → Genera embedding della query concatenando le skill normalizzate
3. **Search** → Cosine similarity su `cv_skills` con filtri opzionali (domain, seniority, availability)
4. **Score** → `final_score = 0.7 * cosine_similarity + 0.3 * match_ratio`
5. **Rank** → (Opzionale) LLM Decision Engine per re-ranking dei top candidati

Il **match_ratio** è calcolato come `matched_skills / query_skills`, dove matched_skills sono le skill della query presenti nel payload `normalized_skills` del punto.

---

## 3. Gap Analysis

L'analisi dei gap confronta le capacità attuali con il modello target di ricerca skill-first con experience enrichment e reskilling predittivo.

### 3.1 Ricerca e Ranking

| Area | Stato Attuale | Gap Identificato | Impatto |
|---|---|---|---|
| Scoring formula | `0.7 similarity + 0.3 match_ratio` | Non distingue tra skill primarie e secondarie; non pesa la profondità dell'esperienza | ALTO |
| Experience enrichment | Collection separata, non integrata nello scoring | Le esperienze non rafforzano il ranking dei candidati con skill verificate da esperienza reale | ALTO |
| Reskilling integration | CSV esportato ma non indicizzato | Nessuna proiezione predittiva su skill in costruzione; dati non utilizzati nella ricerca | MEDIO |
| Multi-vector search | Solo `cv_skills` usata per search | `cv_experiences` non contribuisce al ranking finale; nessun cross-collection scoring | ALTO |
| Profile evaluation | Nessuna API dedicata | Impossibile ottenere statistiche aggregate o score di valutazione per un singolo profilo | MEDIO |

### 3.2 Ingestion e Dati

| Area | Stato Attuale | Gap Identificato | Impatto |
|---|---|---|---|
| Reskilling data model | CSV export generico | Dati non strutturati in modello dedicato; nessun mapping skill target → skill normalizzate | MEDIO |
| Skill weighting | Tutte le skill hanno peso uguale | Nessuna distinzione tra core skill e nice-to-have; skill di 10 anni e 1 anno pesano uguale | ALTO |
| Experience depth | Testo libero per esperienza | Non si estrae durata, ruolo specifico, impatto; collegamento skill → esperienza debole | MEDIO |
| Workflow resilience | Chord strict: 1 fallimento blocca tutto | Reskilling timeout causa ChordError che blocca `embed_all` | ALTO |

---

## 4. Architettura TO-BE

La proposta evolutiva si articola in quattro macro-aree, ciascuna indipendente ma sinergica.

### 4.1 Multi-Layer Search Engine

Il cuore della proposta è un motore di ricerca **multi-layer** che combina i risultati di più collection Qdrant con pesi configurabili.

#### 4.1.1 Layer 1: Skill Matching (Primario)

Rimane il layer dominante. Le skill della query vengono normalizzate e matchate contro `cv_skills`. Evoluzione proposta:

| Miglioramento | Descrizione | Formula |
|---|---|---|
| Weighted Skills | Skill pesate per anni di esperienza e certificazioni | `skill_weight = base + log(1 + years) + cert_bonus` |
| Domain Boost | Boost per skill nello stesso dominio della query | `domain_score * 1.2` se domain match |
| Seniority Alignment | Penalizzazione per mismatch di seniority | `penalty = abs(query_seniority - profile_seniority) * 0.05` |

#### 4.1.2 Layer 2: Experience Validation (Secondario)

Le esperienze dalla collection `cv_experiences` vengono usate per **validare e rafforzare** il match skill-based. Un candidato con le skill giuste E esperienze rilevanti riceve un boost significativo.

**Algoritmo proposto:**

1. Per ogni candidato dal Layer 1, cercare esperienze correlate in `cv_experiences`
2. Calcolare un **experience_relevance_score** basato su: cosine similarity esperienza-query, numero di skill matchate nell'esperienza, durata dell'esperienza
3. Applicare il boost: `final_score = skill_score * (1 + experience_boost * 0.3)`

#### 4.1.3 Layer 3: Reskilling Trajectory (Predittivo)

Nuova collection **cv_reskilling** che indicizza le skill in costruzione. Questo layer non altera il ranking primario ma aggiunge **metadati predittivi** alla risposta:

| Campo | Tipo | Descrizione |
|---|---|---|
| `skills_in_progress` | `List[str]` | Skill attualmente in fase di acquisizione |
| `process_type` | `str` | Tipo di processo formativo (corso, certificazione, mentoring) |
| `estimated_completion` | `date | null` | Data stimata di completamento se disponibile |
| `trajectory_score` | `float` | Score 0-1 che indica quanto il profilo si sta muovendo verso le skill richieste |

#### 4.1.4 Formula di Scoring Composita

La formula finale combina i tre layer con pesi configurabili:

```
final_score = W_skill * skill_score + W_exp * experience_boost + W_resk * trajectory_bonus

Default weights: W_skill = 0.60, W_exp = 0.30, W_resk = 0.10

Dove skill_score include: cosine_similarity, match_ratio, weighted_skills, domain_boost
```

### 4.2 Enriched Search Response

La risposta della ricerca viene arricchita con informazioni multi-dimensionali per ogni candidato:

| Sezione | Contenuto | Fonte |
|---|---|---|
| `skills_match` | Lista skill matchate con peso e livello, skill mancanti | `cv_skills` + scoring |
| `experience_context` | Top 3 esperienze rilevanti con durata e ruolo | `cv_experiences` |
| `reskilling_outlook` | Skill in costruzione, tipo processo, trajectory score | `cv_reskilling` (nuovo) |
| `availability` | Stato corrente: FREE/PARTIAL/BUSY/UNAVAILABLE | Redis cache |
| `profile_summary` | Seniority, domain principale, anni tot esperienza | NormalizedDocument metadata |

Questo modello di risposta permette al consumer di avere una vista **olistica** del candidato senza dover fare chiamate aggiuntive per ottenere il contesto delle esperienze o lo stato del reskilling.

### 4.3 Profile Statistics & Evaluation API

Nuova API separata dalla ricerca, dedicata all'analisi e valutazione di un singolo profilo. Endpoint proposto: **GET /api/v1/profiles/{res_id}/stats**

#### 4.3.1 Skill Assessment

| Metrica | Descrizione | Calcolo |
|---|---|---|
| `skill_coverage` | Copertura skill rispetto a un benchmark di ruolo | `matched_skills / role_required_skills` |
| `skill_depth` | Profondità media delle competenze | `avg(years_per_skill * cert_multiplier)` |
| `skill_breadth` | Ampiezza del portfolio skill | `unique_domains / total_domains_in_taxonomy` |
| `skill_freshness` | Quanto recenti sono le skill (decay temporale) | `sum(skill_weight * recency_factor)` |

#### 4.3.2 Experience Assessment

| Metrica | Descrizione |
|---|---|
| `total_years` | Anni totali di esperienza professionale |
| `domain_concentration` | Concentrazione su domini specifici vs generalismo |
| `role_progression` | Evoluzione dei ruoli (junior → senior → lead) |
| `project_diversity` | Varietà di tipologie di progetto e settori |

#### 4.3.3 Growth Trajectory

Basato sui dati di reskilling, fornisce una proiezione del percorso di crescita:

| Metrica | Descrizione |
|---|---|
| `skills_in_progress` | Skill attualmente in fase di acquisizione con tipo processo |
| `predicted_skills_6m` | Skill probabilmente acquisite entro 6 mesi |
| `career_direction` | Direzione del percorso: specializzazione vs broadening |
| `reskilling_velocity` | Velocità di acquisizione nuove skill (skill/anno) |

### 4.4 Evoluzione Qdrant Collections

La proposta prevede l'aggiunta di una terza collection e l'arricchimento dei payload esistenti:

| Collection | Stato | Evoluzione |
|---|---|---|
| `cv_skills` | Esistente | Aggiungere: `skill_weights` (dict), `domain_primary`, `total_experience_years`, `certification_count` |
| `cv_experiences` | Esistente | Aggiungere: `duration_months`, `role_title`, `industry_sector`, `project_type` |
| `cv_reskilling` | **NUOVA** | Campi: `res_id`, `skills_in_progress`, `process_type`, `start_date`, `estimated_end`, `skill_targets_normalized` |

La collection **cv_reskilling** usa lo stesso modello di embedding delle altre collection per consentire ricerche semantiche cross-collection. L'ID è deterministico: `uuid5(NAMESPACE, f"{res_id}:reskilling")`.

### 4.5 Workflow Resilience

Il problema attuale: il fallimento del task **export_reskilling** (timeout dopo 3 retry) causa un **ChordError** che blocca **embed_all**, impedendo l'aggiornamento degli embedding anche quando tutti gli altri task sono completati con successo.

#### 4.5.1 Pattern: Best-Effort Chord

Sostituire il chord strict con un pattern best-effort che:

| Comportamento | Chord Strict (AS-IS) | Best-Effort Chord (TO-BE) |
|---|---|---|
| 1 task fallisce | ChordError, callback non eseguito | Callback eseguito con risultati parziali |
| Dati reskilling non disponibili | Embedding non aggiornati per nessuno | Embedding aggiornati per skills ed experiences |
| Retry strategy | Task-level con countdown fisso | Task-level + circuit breaker per endpoint problematici |
| Monitoring | Nessuno | Metriche per task success rate, partial completion alerts |

**Implementazione suggerita:** Wrappare ogni task del chord con un error handler che ritorna un risultato di fallback (es. `None` o empty dict) invece di propagare l'eccezione. Il callback `embed_all` controlla quali risultati sono disponibili e processa solo quelli validi.

#### 4.5.2 Pattern: Fetch/Refresh Decoupling (Issue #65 — P0-critical)

Problema attuale più critico del ChordError: il task `scraper.inside_refresh` contiene un loop sincrono che itera su TUTTI i res_id (~100 profili), chiamando `refresh_inside_cv()` per ciascuno. Un singolo ReadTimeout (dopo ~500s) causa il retry dell'intero task da zero, vanificando tutto il lavoro già completato. Inoltre, il workflow successivo (`inside_fanout`) ricrea task individuali per gli stessi res_id, duplicando l'elaborazione.

**Soluzione approvata (3 fasi):**

**Fase 1 — Disaccoppiare fetch da refresh:** `scraper.inside_refresh` deve fare SOLO:
1. Chiamare `fetch_inside_res_ids()` per ottenere la lista
2. Salvare i res_id in Redis con `cache.set_res_ids()`
3. Restituire il risultato senza processare i profili

Il loop di refresh viene completamente rimosso.

**Fase 2 — Delegare al fanout:** Il workflow `res_id_workflow.yaml` già prevede il fanout verso `scraper.inside_refresh_item`. Eliminando il loop dal task padre, ogni profilo viene processato UNA sola volta come task individuale con retry indipendente, parallelismo tramite i worker Celery e progresso incrementale (se un profilo fallisce, gli altri non sono impattati).

**Fase 3 — Timeout aggressivo:** Con il loop rimosso, `inside_refresh` diventa una singola chiamata HTTP leggera. Il timeout può essere ridotto da 120s a 30s. Questo fix è prerequisito per la Phase 1 della roadmap evolutiva.

**File coinvolti:**
- `src/services/scraper/tasks.py` — rimuovere il loop da `scraper_inside_refresh_task`
- `config/workflows/res_id_workflow.yaml` — nessuna modifica necessaria, già corretto
- `src/services/scraper/client.py` — opzionale: timeout configurabile

---

## 5. Enhanced Ingestion Pipeline

### 5.1 Skill Extraction Potenziato

L'estrazione skill via LLM deve essere arricchita per supportare il weighted scoring:

| Campo Attuale | Evoluzione Proposta |
|---|---|
| `skill_name: str` | `skill_name: str` + `skill_weight: float` (calcolato) |
| `normalized_skills: List[str]` | `weighted_skills: Dict[str, SkillWeight]` con years, level, certified |
| `skill_domain: str` | `skill_domains: List[str]` con `primary_domain` flag |
| `seniority_bucket: str` | `seniority_bucket: str` + `seniority_evidence: List[str]` |

Il modello **SkillWeight** proposto:

```python
class SkillWeight(BaseModel):
    name: str                    # Skill normalizzata
    years: float = 0.0           # Anni di esperienza sulla skill
    level: str = "intermediate"  # junior/intermediate/senior/expert
    certified: bool = False      # Ha certificazione sulla skill
    from_experience: bool = True # Skill verificata da esperienza
    weight: float                # Peso calcolato: base + log(1+years) + cert_bonus
```

### 5.2 Reskilling Data Ingestion

Attualmente il CSV di reskilling viene solo esportato. La proposta prevede:

1. **Parsing strutturato** → Estrarre dal CSV: res_id, tipo processo, skill target, data inizio, stato
2. **Skill normalization** → Mappare le skill target del reskilling al dizionario canonico (SkillNormalizer)
3. **Embedding** → Generare embedding per le skill in costruzione e indicizzare in `cv_reskilling`
4. **Profile linking** → Collegare i dati reskilling al profilo tramite res_id per la Profile Statistics API

### 5.3 Experience Extraction Potenziato

L'estrazione delle esperienze deve produrre metadati strutturati aggiuntivi:

| Campo | Tipo | Estrazione | Uso |
|---|---|---|---|
| `duration_months` | int | LLM da date inizio/fine nel CV | Peso esperienza nello scoring |
| `role_title` | str | LLM dal titolo della posizione | Matching per ruolo |
| `industry` | str | LLM dal contesto aziendale | Filtro per settore |
| `skills_applied` | `List[str]` | Cross-reference con skill estratte | Validazione skill tramite esperienza |
| `impact_level` | str | LLM: individual/team/department/company | Seniority evidence |

---

## 6. API Design

### 6.1 Search API Evoluta

Endpoint: **POST /api/v1/search/skills** (retrocompatibile, con nuovi campi opzionali)

```python
class SkillSearchRequest(BaseModel):
    skills: List[str]                          # Required: skill da cercare
    filters: SearchFilters | None              # Filtri esistenti

    # --- Nuovi campi opzionali ---
    include_experiences: bool = True            # Arricchisci con esperienze
    include_reskilling: bool = True             # Includi reskilling outlook
    scoring_weights: ScoringWeights | None      # Override pesi scoring
    min_experience_years: int | None            # Filtro anni esperienza min
```

### 6.2 Profile Statistics API

Endpoint: **GET /api/v1/profiles/{res_id}/stats**

Response model proposto:

```python
class ProfileStats(BaseModel):
    res_id: int
    skill_assessment: SkillAssessment       # coverage, depth, breadth, freshness
    experience_assessment: ExpAssessment     # total_years, progression, diversity
    growth_trajectory: GrowthTrajectory      # in_progress, predicted, direction
    availability: AvailabilityStatus         # Stato corrente
    overall_score: float                     # Score composito 0-100
```

---

## 7. Implementation Roadmap

La roadmap è organizzata in fasi incrementali, ciascuna rilasciabile indipendentemente:

| Fase | Sprint | Deliverable | Dipendenze | Rischio |
|---|---|---|---|---|
| **Phase 1: Foundation** | S9-S10 | Workflow resilience (best-effort chord), SkillWeight model, enhanced skill extraction | Nessuna | Basso |
| **Phase 2: Experience Layer** | S11-S12 | Experience enrichment nello scoring, metadata strutturati esperienze, cross-collection search | Phase 1 | Medio |
| **Phase 3: Reskilling** | S13-S14 | cv_reskilling collection, reskilling ingestion pipeline, trajectory scoring | Phase 1 | Medio |
| **Phase 4: Profile API** | S15-S16 | Profile Statistics API, skill/experience/growth assessment, overall score | Phase 2 + 3 | Basso |
| **Phase 5: Optimization** | S17-S18 | Tuning pesi scoring, A/B testing, caching strategico, performance optimization | Phase 4 | Basso |

### 7.1 Phase 1: Foundation (Sprint 9-10)

| Task | Effort | Descrizione |
|---|---|---|
| Best-effort chord pattern | 3d | Wrapper per task con fallback, embed_all con risultati parziali |
| SkillWeight model | 2d | Nuovo modello Pydantic con calcolo peso |
| Enhanced LLM extraction prompt | 2d | Aggiornare prompt per estrarre years, level, certified per ogni skill |
| cv_skills payload evolution | 1d | Aggiungere weighted_skills, domain_primary, total_experience_years |
| Scoring formula update | 2d | Implementare weighted scoring con domain boost |
| Test suite | 2d | Unit + integration test per nuovo scoring e workflow |

### 7.2 Phase 2: Experience Layer (Sprint 11-12)

| Task | Effort | Descrizione |
|---|---|---|
| Enhanced experience extraction | 3d | Estrarre duration, role, industry, skills_applied via LLM |
| cv_experiences payload update | 1d | Aggiungere nuovi campi al payload Qdrant |
| Cross-collection search | 3d | Query cv_experiences per candidati dal Layer 1, calcolo experience_boost |
| Enriched response model | 2d | Aggiungere experience_context alla SearchResponse |
| Test suite | 2d | Test cross-collection, scoring composito, response enrichment |

### 7.3 Phase 3: Reskilling Integration (Sprint 13-14)

| Task | Effort | Descrizione |
|---|---|---|
| Reskilling CSV parser | 2d | Parsing strutturato del CSV con mapping a modello dedicato |
| cv_reskilling collection | 2d | Setup Qdrant collection, embedding pipeline, payload indexes |
| Skill normalization mapping | 2d | Mappare skill target reskilling al dizionario canonico |
| Trajectory scoring | 2d | Calcolo trajectory_score basato su overlap skill richieste / in costruzione |
| Reskilling in search response | 1d | Aggiungere reskilling_outlook alla risposta |
| Test suite | 2d | Test ingestion reskilling, trajectory scoring, response |

---

## 8. Architecture Decision Records

### 8.1 ADR-001: Multi-Collection vs Single-Collection Search

| Aspetto | Dettaglio |
|---|---|
| **Status** | Proposed |
| **Context** | Servono dati da skill, esperienze e reskilling per costruire il ranking composito |
| **Decision** | Mantenere collection separate con cross-collection query orchestrata dal search service |
| **Alternative** | Single collection con payload unificato (scartata: payload troppo pesante, aggiornamenti parziali costosi) |
| **Conseguenze +** | Aggiornamento indipendente per collection, query specifiche ottimizzate, scaling indipendente |
| **Conseguenze -** | Latenza aggiuntiva per cross-collection query, complessità orchestrazione |

### 8.2 ADR-002: Scoring Weights Configurabili

| Aspetto | Dettaglio |
|---|---|
| **Status** | Proposed |
| **Context** | I pesi dello scoring composito devono poter essere tunati senza deploy |
| **Decision** | Pesi configurabili via Settings (env vars) con override per-request |
| **Alternative** | Pesi hardcoded (scartata: troppo rigido), ML-learned (prematura per MVP) |
| **Conseguenze +** | A/B testing facilitato, tuning rapido, personalizzazione per use case |
| **Conseguenze -** | Maggiore superficie di configurazione, rischio misconfiguration |

### 8.3 ADR-003: Best-Effort Chord Pattern

| Aspetto | Dettaglio |
|---|---|
| **Status** | Proposed |
| **Context** | Il fallimento di un singolo task (reskilling timeout) blocca l'intera pipeline di embedding |
| **Decision** | Wrappare task del chord con error handler che ritorna fallback instead of raising |
| **Alternative** | Separare workflow in pipeline indipendenti (scartata: duplicazione logica, sync complessa) |
| **Conseguenze +** | Pipeline sempre eseguita, dati parziali meglio di nessun dato, monitoring su partial failures |
| **Conseguenze -** | Possibilità di dati stale per dimensioni fallite, necessità di alerting |

### 8.4 ADR-004: Fetch/Refresh Decoupling in scraper.inside_refresh

| Aspetto | Dettaglio |
|---|---|
| **Status** | **Accepted (P0-critical) — Issue #65** |
| **Context** | `scraper.inside_refresh` esegue un loop sincrono su ~100 profili in un singolo task Celery (500s+), poi il fanout duplica lo stesso lavoro con task individuali. Un ReadTimeout uccide tutto il progresso. |
| **Decision** | Disaccoppiare fetch (solo recupero lista res_id + cache Redis) da refresh (delegato interamente al fanout tramite task `inside_refresh_item` individuali) |
| **Alternative** | Batch chunking nel loop (scartata: complessità aggiunta senza eliminare il problema del single-point-of-failure) |
| **Conseguenze +** | Eliminazione double processing, retry indipendente per profilo, parallelismo pieno, timeout task padre < 30s, nessun lavoro perso al retry |
| **Conseguenze -** | Nessuna significativa: il workflow già prevede il fanout; la modifica rimuove codice ridondante |

---

## 9. Rischi e Mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| LLM extraction quality | Media | Alto | Validation layer post-extraction, fallback su regex per campi strutturati, prompt engineering iterativo |
| Cross-collection latency | Media | Medio | Caching aggressivo Layer 1 results, parallel queries, limit top-K per Layer 2 |
| Reskilling data incompletezza | Alta | Basso | Graceful degradation: se reskilling non disponibile, `trajectory_score = null`, non 0 |
| Scoring weights tuning | Bassa | Medio | Default conservativi (skill-first), A/B testing framework, rollback rapido via env vars |
| Backward compatibility | Bassa | Alto | Nuovi campi opzionali, default behavior = AS-IS, feature flags per nuovi layer |

---

## 10. Conclusioni e Next Steps

L'architettura proposta evolve ProfileBot da un motore di ricerca **flat-text** a un sistema **multi-dimensionale skill-first** che sfrutta appieno i dati già disponibili. I principi guida sono:

- **Incrementalità**: ogni fase è rilasciabile indipendentemente e retrocompatibile
- **Resilienza**: la pipeline tolera fallimenti parziali senza compromettere l'intero sistema
- **Configurabilità**: pesi, layer e arricchimenti sono tutti configurabili senza deploy
- **Pragmatismo**: le fonti dati sono quelle esistenti (CV, availability, reskilling), nessuna nuova integrazione richiesta

**Immediate next steps:**

1. Validare la proposta con il team e raccogliere feedback
2. Creare le GitHub issues per la Phase 1 (Foundation)
3. Implementare il best-effort chord pattern come quick win
4. Prototipare il SkillWeight model e testare l'enhanced extraction
