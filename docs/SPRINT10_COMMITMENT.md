# Sprint 10 Commitment — Phase 1 Foundation: KP Data Layer & Hybrid Search

> **Sprint:** 10
> **Milestone GitHub:** Sprint 10 - KP Foundation & Semantic Fallback
> **Durata:** 2 settimane (9 mar – 22 mar 2026)
> **Velocity target:** 16 SP (media storica: ~19 SP/sprint, buffer per complessità LLM)
> **Tema:** Completare Phase 1 Foundation (Architecture Analysis §7.1) e attivare il Layer 2 Hybrid Context (#63) nel framework Multi-Layer Search Engine

---

## Visione Multi-Sprint

> **Questo sprint non è una feature isolata.** È il primo mattone operativo della visione TO-BE definita in Architecture Analysis §4 e LLM-study §3-§6.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VISIONE TO-BE COMPLETA                           │
│                                                                     │
│  Ricerca multi-layer (skill + experience + reskilling)              │
│  × KP completo (4 sorgenti: Qdrant, Dictionary, Redis, Reskilling) │
│  × LLM multi-scenario (matching, gap, reskilling, team, report)    │
│  × Availability come vincolo + IC sub-state                        │
│  × Explainability (source attribution, confidence, red flags)      │
│  × Potenzialità (reskilling trajectory, skill in acquisizione)     │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──── SPRINT 10 (questo) ─────────────────────────────────────────────┐
│  Phase 1 Foundation — DATA LAYER                                    │
│  ├── SkillWeight model (skill pesate, non più flat list)            │
│  ├── Seniority calculator (non più "unknown")                       │
│  ├── Config LLM (parametri configurabili)                           │
│  ├── Scoring evoluto (weighted + domain boost)                      │
│  ├── #63: Layer 2 entry point — skills_dictionary (Opz. A)         │
│  │        + cv_chunks collection (Opz. C)                           │
│  │        + fusione risultati (RRF/weighted)                        │
│  └── Test coverage ≥ 80%                                            │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──── SPRINT 11 ──────────────────────────────────────────────────────┐
│  Phase 1 completion + KP Builder (LLM-study Fase 2)                 │
│  ├── Reskilling infrastructure (cache, service, Celery task)        │
│  ├── IC sub-state calculator                                        │
│  ├── KnowledgeProfile schema completo                               │
│  ├── KP Builder (assembla da 4 sorgenti)                            │
│  └── Benchmark search (#34) con scoring evoluto                     │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──── SPRINT 12 ──────────────────────────────────────────────────────┐
│  Context Builder + Multi-Scenario Prompting (LLM-study Fase 2-3)    │
│  ├── KPContextBuilder (serializzazione KP → testo per LLM)         │
│  ├── Token budget manager                                           │
│  ├── Scenario 1: Matching evoluto (con KP completo)                 │
│  ├── Scenario 3: Gap Analysis                                       │
│  └── Output: confidence, decision_reason, alternatives, red flags   │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──── SPRINT 13-14 ───────────────────────────────────────────────────┐
│  Phase 2-3: Experience Layer + Reskilling Trajectory                 │
│  ├── Cross-collection search (cv_experiences nel ranking)           │
│  ├── cv_reskilling collection + trajectory scoring                  │
│  ├── Scenario 2: Reskilling Suggestion                              │
│  ├── Scenario 4: Team Planning                                      │
│  └── Scenario 5: Reportistica                                       │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──── SPRINT 15-18 ───────────────────────────────────────────────────┐
│  Phase 4-5: Profile API + Optimization                              │
│  ├── Profile Statistics & Evaluation API                            │
│  ├── Scoring tuning con A/B testing                                 │
│  ├── Semantic cache (Redis)                                         │
│  └── UI: Visualizzazione Profili, Chat, Source Attribution          │
└─────────────────────────────────────────────────────────────────────┘
```

**Cosa abilita ogni sprint per la visione completa di Giamma:**

| Capacità desiderata | Dove si costruisce |
|--------------------|--------------------|
| Ricerche indirizzate per **skill** con profondità (anni, livello, certificazioni) | **S10** — SkillWeight + scoring evoluto |
| Ricerche che incrociano **esperienze** | S13 — Experience Layer (cross-collection search) |
| Incrocio con **availability** e vincoli | Già operativo + **S11** con IC sub-state |
| Cercare profili in **reskilling** (competenze in apprendimento) | S11 — Reskilling infra + **S13** — cv_reskilling + trajectory |
| **Analisi profonda JD** con consigli e valutazioni | S12 — Multi-Scenario Prompting (matching + gap analysis) |
| **Workaround/fallback** con grado di rischio | **S10** — #63 fallback semantico + **S12** — confidence levels |
| **Potenzialità** nei profili | S11 — reskilling trajectory + **S13** — trajectory scoring |
| **Red flag** nei profili | S12 — LLM con KP completo (seniority mismatch, bassa confidence, IC in transizione) |

---

## Sprint Goal

**Costruire il data layer del Knowledge Profile e attivare il Layer 2 Hybrid Search**, completando la Phase 1 Foundation (Architecture Analysis §7.1) e implementando il fallback semantico (#63) come **primo caso d'uso operativo** del Multi-Layer Search Engine.

Al termine dello sprint:
- Il modello `SkillWeight` produce skill pesate (anni, livello, certificazioni) — non più flat list
- La seniority è calcolata per ogni profilo — non più `"unknown"`
- La collection `skills_dictionary` in Qdrant permette recovery semantico di skill dalla JD (Opzione A)
- La collection `cv_chunks` abilita ricerca testuale parallela sui CV (Opzione C)
- La fusione RRF/weighted produce output separati: `candidates_by_skills`, `candidates_by_chunks`, `candidates_fused`
- La formula di scoring è evoluta a weighted skills + domain boost + seniority alignment

---

## Contesto e Motivazione

### Dove siamo nella roadmap

L'Architecture Analysis §7 definisce 5 fasi. Sprint 9 ha completato la parte resilienza della Phase 1:

| Phase 1 — Foundation (S9-S10) | Stato |
|-------------------------------|:-----:|
| Best-effort chord pattern | ✅ Sprint 9 (TD-007) |
| Fetch/Refresh decoupling | ✅ Sprint 9 (TD-006) |
| **SkillWeight model** | **Sprint 10** |
| **Enhanced LLM extraction prompt** | **Sprint 10** |
| **cv_skills payload evolution** | **Sprint 10** |
| **Scoring formula update** | **Sprint 10** |

Parallelamente, il LLM-study §12 elenca 12 gap. Sprint 10 affronta:

| # | Gap (LLM-study §12) | Priorità | Sprint 10 |
|:-:|------|:--------:|:---------:|
| 1 | Reskilling infrastructure assente | Critico | Parziale — solo schema + normalizer (Fase 1 LLM-study §13) |
| 2 | Seniority bucket sempre "unknown" | Critico | **Sì** |
| 3 | DecisionCandidate troppo scarno | Critico | Preparatorio — SkillDetail con metadata |
| 4 | Config.py senza campi LLM | Critico | **Sì** |

### #63 come Layer 2 Entry Point

L'issue #63 (fallback semantico) **non è una feature a sé**. È il **primo caso d'uso operativo del Layer 2 della strategia Hybrid Context** (LLM-study §5):

- **Layer 1** (skill matching su `cv_skills`) è l'attuale sistema di ricerca → **evoluto in S10** con SkillWeight e scoring
- **Layer 2** (experience/chunk validation) è la ricerca parallela su testo → **attivato in S10** via #63 con `cv_chunks` + `skills_dictionary`
- **Layer 3** (reskilling trajectory) è il livello predittivo → **Sprint 13** con `cv_reskilling`

Il trigger di #63 (`normalized_skills == []`) è il caso d'uso più urgente, ma l'infrastruttura chunk creata serve l'intera visione Hybrid Context: il KP Builder (Sprint 11) userà `cv_chunks` per il campo `relevant_chunks` del KnowledgeProfile (LLM-study §3.2), e il Context Builder (Sprint 12) lo serializzerà per l'LLM.

### Decisione architetturale: Opzione A + C

**Decisione presa in planning:** adottare **Opzione A + C** per coerenza architetturale.

| Opzione | Cosa fa | Pro | Contro | Decisione |
|---------|---------|-----|--------|:---------:|
| **A** — `skills_dictionary` collection | Embed skill canoniche → collection dedicata; quando `normalized_skills == []`, embed JD → query dictionary → top-K skill | Pulita, indipendente dai CV, deterministico, allineata al layer di normalizzazione | Pre-computing iniziale, mantenimento se dizionario cambia | **Sì** ✅ |
| **B** — Fallback su `cv_skills` | Embed JD → query diretta cv_skills → estrarre skill frequenti | Rapida, nessuna nuova collection | Mescola fallback e retrieval nello stesso layer, dipende dal dataset | **No** ❌ |
| **C** — `cv_chunks` collection | Chunk testuali CV → collection dedicata; ricerca parallela su testo | Abilita Layer 2 Hybrid Context, base per KP builder | Nuova collection, pipeline embedding aggiuntiva | **Sì** ✅ |

**Motivazione:** Opzione B è un workaround che mescola i layer. Opzione A mantiene la separazione: il dizionario skill è un layer di normalizzazione semantica indipendente dai CV. Costo aggiuntivo modesto: le skill canoniche sono centinaia (non migliaia), il pre-computing è un job una tantum.

### Prerequisiti completati

- ✅ Pipeline stabile (TD-006 + TD-007)
- ✅ Dati Qdrant affidabili e consistenti
- ✅ BestEffortChord disponibile per parallelismo
- ✅ Monitoring attivo (OBS-066)
- ✅ `cv_experiences` già indicizzata (base per `cv_chunks`)
- ✅ Skill dictionary YAML versionato (base per `skills_dictionary` collection)

### Riferimenti architetturali

| Documento | Sezioni rilevanti |
|-----------|-------------------|
| `docs/ProfileBot_Architecture_Analysis.md` | §4.1 Multi-Layer Search, §4.1.1 Layer 1 Skill Matching, §4.1.4 Scoring Composita, §4.4 Evoluzione Collections, §5.1 Skill Extraction Potenziato, §7.1 Phase 1 Foundation |
| `docs/LLM-study.md` | §2.1 Pipeline CV, §3 KP Model, §3.2 KP Schema (RelevantChunk), §3.4 Seniority Calculator, §5 Hybrid Context, §5.3 Strategia hybrid, §5.4 Quando attivare chunk, §12 Gap Analysis, §13 Roadmap Fase 1 |
| `docs/appendice_tecnica_indexing.md` | §A.2 HNSW, §B Context normalization, §C.3 Source attribution |
| ADR-003 | Best-Effort Chord (implementato) |
| ADR-004 | Fetch/Refresh Decoupling (implementato) |

---

## Stato Issue

| # | Issue | GitHub | SP | Priorità | Dipendenze | Branch proposto |
|---|-------|--------|----|----------|------------|-----------------|
| 1 | **#63** Fallback semantico — Layer 2 entry point | [#63](https://github.com/giamma80/profilebot/issues/63) | 8 | P0 | Pipeline stabile ✅ | `feature/63-semantic-fallback` |
| 2 | **#71** SkillWeight + Seniority + Scoring evoluto | [#71](https://github.com/giamma80/profilebot/issues/71) | 5 | P0 | — | `feature/71-skillweight-scoring` |
| 3 | **#24** Test Coverage Improvement | [#24](https://github.com/giamma80/profilebot/issues/24) | 3 | P1 | — | `chore/24-test-coverage` |
| | **TOTALE** | | **16** | | | |

> **Nota:** L'issue #71 "SkillWeight + Seniority + Scoring evoluto" raggruppa i task residui della Phase 1 Foundation (Architecture Analysis §7.1) e i gap critici #2 e #4 del LLM-study §12. Milestone: Sprint 10 - KP Foundation & Semantic Fallback (Milestone #8).

---

## Sequenza di Lavoro

```
Week 1 (giorni 1-5)
├── SkillWeight + Seniority ──────────────── [giorno 1-3]
│   ├── SkillWeight model Pydantic (Arch §5.1)
│   │   weight = base + log(1 + years) + cert_bonus
│   ├── Enhanced LLM extraction prompt:
│   │   estrarre years, level, certified per ogni skill
│   ├── Seniority calculator (LLM-study §3.4)
│   │   euristica: years + skills_count + management_keywords
│   ├── Config.py: campi LLM + search (gap #4 LLM-study §12.1)
│   ├── cv_skills payload evolution: weighted_skills, domain_primary
│   └── Test unitari SkillWeight + seniority
│
├── #63 Fase 1: skills_dictionary (Opz. A) ── [giorno 3-4]
│   ├── Creare collection Qdrant `skills_dictionary`:
│   │   embed ogni skill canonica dal dizionario YAML
│   ├── Job di pre-computing (one-shot + aggiornamento su cambio YAML)
│   ├── Quando normalized_skills == []:
│   │   embed JD → query skills_dictionary → top-K skill simili
│   │   → rilancia search_by_skills con skill recuperate
│   ├── Almeno 1 skill canonica per JD generiche
│   ├── Logging esplicito: "FALLBACK_SKILL_RECOVERY activated"
│   ├── no_match_reason se nessun match nemmeno con fallback
│   └── Test: JD senza skill riconosciute → fallback → skill recuperate
│
└── #63 Fase 2: cv_chunks Collection (Opz. C) ─ [giorno 4-5]
    ├── Riusare/estendere EmbeddingPipeline._build_experience_points
    │   come base per chunk generici (non solo esperienze)
    ├── Estendere a: summary CV, education, certificazioni, testo generico
    ├── Collection cv_chunks: payload {res_id, section_type, chunk_index, text_preview}
    ├── Integrazione nel workflow post-refresh con BestEffortChord
    └── Test: CV processato → chunk indicizzati in cv_chunks

Week 2 (giorni 6-10)
├── #63 Fase 3: Ricerca parallela + Fusione ── [giorno 6-8]
│   ├── Search flow:
│   │   1. skill search (Layer 1, con scoring evoluto)
│   │   2. IF normalized_skills == []: skill recovery via skills_dictionary
│   │   3. chunk search parallelo su cv_chunks (Layer 2)
│   │   4. fusione con strategia RRF o weighted score
│   ├── Output separato:
│   │   candidates_by_skills, candidates_by_chunks, candidates_fused
│   ├── Filtro idoneità: 1 must-have matchata OR match_ratio >= 0.4
│   ├── Non regressione: se skill valide, Layer 2 è complementare (non sostitutivo)
│   ├── Metriche Prometheus: search_fallback_activated_total,
│   │   search_chunk_results_count, search_fusion_used_total
│   └── Integration test e2e fallback
│
├── Scoring Formula Update ────────────────── [giorno 8-9]
│   ├── Da: 0.7 * similarity + 0.3 * match_ratio
│   ├── A:  W_skill * weighted_skill_score + domain_boost - seniority_penalty
│   │   (Arch §4.1.1, §4.1.4)
│   │   domain_boost = domain_score * 1.2 se domain match
│   │   seniority_penalty = abs(query - profile) * 0.05
│   ├── Feature flag: USE_WEIGHTED_SCORING (default off, validare su benchmark)
│   └── Test: scoring regressione + nuovi casi weighted
│
└── #24 Test Coverage ─────────────────────── [giorno 9-10]
    ├── Audit coverage per modulo
    ├── Test per moduli critici sotto 80%
    │   (focus: core/skills/, core/search/, core/embedding/)
    ├── Coverage gate in CI (≥ 80%)
    └── Report coverage HTML come CI artifact
```

### Critical Path

```
[SkillWeight] ──→ [LLM extraction prompt] ──→ [cv_skills payload] ──→ [Scoring Update]
      │                                                                       ↑
      └──→ [Seniority Calc]                                                   │
                                                                              │
[skills_dictionary (A)] ──→ [cv_chunks (C)] ──→ [Fusione (RRF)] ─────────────┘

I due filoni convergono nella Scoring Formula Update (giorno 8-9):
- filone 1 produce skill pesate + seniority → scoring Layer 1 evoluto
- filone 2 produce chunk search + fusione → scoring Layer 2

#24 Test Coverage è indipendente, in parallelo.
```

---

## Dettaglio per Issue

### #71 — SkillWeight + Seniority + Scoring Evoluto (5 SP)

**Obiettivo:** Completare i task residui della Phase 1 Foundation, colmando i gap critici #2 e #4 del LLM-study. Evolvere il Layer 1 Skill Matching da flat list a weighted skill model.

**Ref:** Architecture Analysis §4.1.1, §5.1; LLM-study §3.4, §12.1

#### A. SkillWeight Model (Arch §5.1)

Implementare il modello `SkillWeight` dalla Architecture Analysis:

```python
class SkillWeight(BaseModel):
    name: str                    # Skill normalizzata
    years: float = 0.0           # Anni di esperienza sulla skill
    level: str = "intermediate"  # junior/intermediate/senior/expert
    certified: bool = False      # Ha certificazione sulla skill
    from_experience: bool = True # Skill verificata da esperienza
    weight: float                # Peso calcolato: base + log(1+years) + cert_bonus
```

- Integrazione con `SkillExtractor`: il prompt LLM deve estrarre anni, livello, certificazioni per ogni skill
- Il peso è calcolato: `skill_weight = 1.0 + log(1 + years) + (0.5 if certified else 0)`
- **Questo è il precursore di `SkillDetail`** nel KP (LLM-study §3.2): Sprint 11 lo estenderà con `confidence`, `match_type`, `source`, `reskilling_completion_pct`

**File:** `src/core/skills/weight.py` (nuovo), `src/core/skills/normalizer.py` (evoluzione), `src/core/embedding/pipeline.py` (payload update)

#### B. Seniority Calculator (LLM-study §3.4)

Implementare l'euristica di calcolo seniority definita nel LLM-study:

```python
def calculate_seniority(years_experience, skills_count, has_management_skills, lead_keywords_in_role):
    # ≥12 anni OR (≥8 + lead keywords) → "lead"
    # ≥6 anni → "senior"
    # ≥3 anni → "mid"
    # ≥0 → "junior"
    # Fallback su skills_count se years non disponibili
```

- Eliminare l'hardcoded `"unknown"` in `pipeline.py` linea ~149
- La seniority calcolata diventa dato reale nel KP (Sprint 11) e criterio di scoring (questo sprint)

**File:** `src/core/skills/seniority.py` (nuovo), `src/core/embedding/pipeline.py` (fix)

#### C. Config LLM (LLM-study §12.1 gap #4)

Aggiungere a `core/config.py`:
- `llm_model`, `llm_temperature`, `llm_max_tokens`, `llm_timeout`
- `search_min_skill_score`, `search_fallback_enabled`, `search_chunk_weight`
- `scoring_use_weighted` (feature flag per scoring evoluto)

#### D. Scoring Formula (Arch §4.1.1, §4.1.4)

Evolvere la formula di scoring del Layer 1:
- **Da:** `final_score = 0.7 * cosine_similarity + 0.3 * match_ratio`
- **A:** `final_score = W_skill * weighted_skill_score + domain_boost - seniority_penalty`
  - `weighted_skill_score` usa i pesi di SkillWeight (non più flat average)
  - `domain_boost = domain_score * 1.2` se domain match
  - `seniority_penalty = abs(query_seniority - profile_seniority) * 0.05`
- **Feature flag:** `USE_WEIGHTED_SCORING` (default: off in prod fino a benchmark Sprint 11)

**File:** `src/core/search/scoring.py` (nuovo o refactor), `src/api/routes/search.py`

**Acceptance Criteria:**
- [ ] `SkillWeight` model con calcolo peso automatico
- [ ] Prompt LLM extraction aggiornato per estrarre years/level/certified
- [ ] Seniority calcolata per ogni profilo, non più `"unknown"`
- [ ] cv_skills payload include `weighted_skills`, `domain_primary`, `total_experience_years`
- [ ] Config.py con campi LLM e search configurabili
- [ ] Scoring formula evoluta con weighted skills + domain boost
- [ ] Feature flag per rollback sicuro
- [ ] ≥ 8 test (SkillWeight, seniority, scoring, backward compatibility)

---

### #63 — Fallback semantico — Layer 2 Entry Point (8 SP)

**Obiettivo:** Attivare il Layer 2 del Multi-Layer Search Engine. Quando `normalized_skills == []`, recovery via `skills_dictionary` (Opzione A) + ricerca parallela su `cv_chunks` (Opzione C) con fusione risultati.

**Ref:** Architecture Analysis §4.1 Multi-Layer Search, §4.4 Evoluzione Collections; LLM-study §5 Hybrid Context, §5.4 Attivazione, §3.2 RelevantChunk

**3 Fasi di implementazione:**

**Fase 1 — Skill Recovery via skills_dictionary (Opzione A) [giorni 3-4]:**

Creare la collection `skills_dictionary` in Qdrant:
1. Pre-computing: per ogni skill canonica nel dizionario YAML, generare embedding e upsert
2. Payload: `{canonical_name, domain, aliases_count, related_skills}`
3. Job di aggiornamento se il dizionario YAML cambia (hook su `dictionary_version`)

Logica fallback:
1. `normalized_skills == []` → trigger
2. Embedding dell'intera JD text
3. Query su `skills_dictionary` con top-K (default K=5)
4. Le skill canoniche recuperate diventano input per `search_by_skills`
5. Se nessuna skill recuperata (embedding JD troppo generico) → `no_match_reason = "no_normalizable_skills_even_with_semantic_fallback"`

Requisiti specifici da #63:
- Logging esplicito (`logger.info("FALLBACK_SKILL_RECOVERY via skills_dictionary: recovered [%s]", skills)`)
- Almeno 1 skill canonica per JD generiche se match nel dizionario
- Non regressione: se `normalized_skills` già valide, nessun fallback

**File:** `src/core/search/skill_dictionary_index.py` (nuovo), `src/core/search/fallback.py` (nuovo), `scripts/index_skills_dictionary.py` (nuovo)

**Fase 2 — cv_chunks Collection (Opzione C) [giorni 4-5]:**

Creare la collection `cv_chunks` per chunk testuali:
- **Base:** riusare/estendere `EmbeddingPipeline._build_experience_points` che già produce embedding per esperienze
- Estendere a: summary CV, sezioni education, certificazioni, testo generico
- Payload minimo: `{res_id, section_type, chunk_index, text_preview}`
- ID deterministico: `uuid5(NAMESPACE, f"{cv_id}:chunk:{section_type}:{chunk_index}")`
- Integrazione nel workflow post-refresh con BestEffortChord (TD-007)

> **Nota architetturale**: `cv_experiences` rimane separata (Layer 2 futuro: cross-collection search Sprint 13). `cv_chunks` è il **contenitore generico** per il Livello 2 Hybrid Context — il `RelevantChunk` nel KP (LLM-study §3.2) attingerà da qui.

**File:** `src/core/embedding/chunk_pipeline.py` (nuovo), `src/core/embedding/pipeline.py` (integrazione)

**Fase 3 — Ricerca parallela + Fusione [giorni 6-8]:**

Flow completo allineato al Multi-Layer Search Engine (Arch §4.1):

```
JD input
    │
    ├──→ SkillNormalizer
    │        │
    │        ├── normalized_skills != [] ──→ Layer 1: skill search (cv_skills)
    │        │                                     │
    │        └── normalized_skills == [] ──→ Fallback: skills_dictionary → recovered_skills
    │                                              │
    │                                              └──→ Layer 1: skill search con recovered_skills
    │
    ├──→ Layer 2: chunk search (cv_chunks) ──── parallelo a Layer 1
    │
    └──→ Fusione Layer 1 + Layer 2
              │
              ├── RRF (default): rank-based, nessuna normalizzazione score
              └── Weighted score (alternativa): W_skill * score_L1 + W_chunk * score_L2
```

Output API (da #63):
```python
class SearchResponse(BaseModel):
    candidates_by_skills: list[ProfileMatch]     # Layer 1 results
    candidates_by_chunks: list[ProfileMatch]     # Layer 2 results
    candidates_fused: list[ProfileMatch] | None  # fusione, opzionale
    fallback_activated: bool                     # True se skills_dictionary usato
    recovered_skills: list[str] | None           # skill recuperate dal fallback
    no_match_reason: str | None                  # perché nessun risultato
    fusion_strategy: str | None                  # "rrf" | "weighted" | null
```

Filtro idoneità (da #63):
- **1 must-have skill matchata** OR `match_ratio >= 0.4`
- Applicato post-fusione su `candidates_fused`
- Se nessun candidato passa → `no_match_reason = "below_eligibility_threshold"`

**File:** `src/core/search/fusion.py` (nuovo), `src/core/search/service.py`, `src/api/routes/search.py`, `src/api/schemas/search.py`

**Acceptance Criteria (da #63):**
- [ ] Collection `skills_dictionary` creata con embedding di tutte le skill canoniche
- [ ] Fallback attivato quando `normalized_skills == []`
- [ ] Logging esplicito del fallback con skill recuperate
- [ ] Almeno 1 skill canonica per JD generiche
- [ ] Collection `cv_chunks` creata e popolata dal workflow
- [ ] Ricerca parallela Layer 1 + Layer 2
- [ ] Strategia di fusione implementata (RRF default, weighted configurabile)
- [ ] Non regressione se skill già valide
- [ ] `no_match_reason` se nessun match
- [ ] Filtro idoneità: 1 must-have matchata OR `match_ratio >= 0.4`
- [ ] Output separato: `candidates_by_skills`, `candidates_by_chunks`, `candidates_fused`
- [ ] Metriche Prometheus: `search_fallback_activated_total`, `search_chunk_results_count`, `search_fusion_used_total`
- [ ] ≥ 10 test (skill dictionary indexing, fallback recovery, chunk indexing, fusione, filtro, no_match_reason, non-regressione)

---

### #24 — Test Coverage Improvement (3 SP)

**Obiettivo:** Portare la test coverage complessiva ≥ 80%, con focus sui moduli evoluti in Sprint 9 e 10.

**Deliverable:**
- Audit coverage con `pytest --cov` per modulo
- Test prioritari per: `core/skills/` (SkillWeight, seniority), `core/search/` (scoring, fallback, fusion), `core/embedding/` (chunk pipeline), `tasks/` (workflows, BestEffortChord)
- CI gate: fail se coverage < 80% sui moduli target
- Report HTML come CI artifact

**Acceptance Criteria:**
- [ ] Coverage complessiva ≥ 80%
- [ ] Nessun modulo critico sotto 70%
- [ ] CI coverage gate attivo
- [ ] Report coverage generato

---

## Enriched Response Schema

> **Richiesta di Giamma:** la response dei servizi di ricerca deve tornare un JSON accurato con sezioni semantiche di valutazione, non solo dati grezzi.

### Schema completo (target TO-BE)

La search response per ogni candidato includerà un `CandidateAssessment` strutturato:

```python
class CandidateAssessment(BaseModel):
    """Valutazione strutturata per ogni candidato nella response."""

    # ── SKILL LEVELS ─────────────────────────────────────────
    skill_levels: SkillLevelsBreakdown
    # Sezione: "livelli di skill identificate, canoniche, must have, potenziali"

    # ── CONSOLIDATED ABILITY ─────────────────────────────────
    consolidated: list[ConsolidatedSkill]
    # Sezione: "abilità consolidata"

    # ── RED FLAGS ────────────────────────────────────────────
    red_flags: list[RedFlag]
    # Sezione: "red flag"

    # ── RISK / OPPORTUNITY ───────────────────────────────────
    risk_opportunity: RiskAssessment
    # Sezione: "azzardo"

    # ── RESKILLING INVESTMENT ────────────────────────────────
    reskilling_investment: ReskillingOutlook | None
    # Sezione: "investimento su percorso di reskilling"

    # ── AVAILABILITY ─────────────────────────────────────────
    availability: AvailabilityAssessment
    # Sezione: "availability"


class SkillLevelsBreakdown(BaseModel):
    """Livelli di skill identificate, canoniche, must have, potenziali."""
    canonical: list[SkillMatch]          # skill dal dizionario con match esatto/alias
    must_have: list[SkillMatch]          # skill richieste dalla JD (required)
    nice_to_have: list[SkillMatch]       # skill preferite dalla JD
    potential: list[PotentialSkill]      # skill inferite da esperienze/chunk (Layer 2)
    unknown_in_jd: list[str]             # skill nella JD non riconosciute dal dizionario
    coverage_pct: float                  # % di skill JD coperte

class SkillMatch(BaseModel):
    name: str                            # skill canonica
    domain: str                          # backend|frontend|data|devops|management
    level: str                           # junior|intermediate|senior|expert
    years: float | None                  # anni esperienza
    certified: bool
    weight: float                        # SkillWeight calcolato
    match_confidence: float              # 0-1 dal normalizer
    match_type: str                      # exact|alias|fuzzy|semantic_fallback

class PotentialSkill(BaseModel):
    name: str                            # skill inferita
    source: str                          # "chunk_match" | "experience_inference" | "reskilling"
    confidence: float                    # quanto siamo sicuri che il candidato la possieda
    evidence: str                        # "menzionata in esperienza presso Acme Corp 2023"


class ConsolidatedSkill(BaseModel):
    """Abilità consolidata: skill con esperienza verificata e profonda."""
    name: str
    years: float                         # ≥ 3 per qualificarsi come "consolidata"
    certified: bool
    from_experience: bool                # verificata da esperienze reali
    weight: float
    consolidation_level: str             # "master" (≥8y) | "solid" (≥5y) | "established" (≥3y)


class RedFlag(BaseModel):
    """Segnalazione di rischio nel profilo."""
    type: str                            # seniority_mismatch | skill_decay | availability_risk
                                         # | low_confidence_match | overqualified | ic_in_transition
                                         # | gap_in_must_have | stale_reskilling
    severity: str                        # high | medium | low
    description: str                     # spiegazione leggibile
    affected_skills: list[str] | None    # skill coinvolte nel red flag


class RiskAssessment(BaseModel):
    """Valutazione azzardo: rischio vs opportunità del candidato."""
    risk_level: str                      # low | medium | high
    risk_factors: list[str]              # fattori di rischio
    opportunity_factors: list[str]       # fattori di opportunità
    azzardo_note: str | None             # nota sintetica ("candidato con high potential
                                         #   ma 2 must-have coperte solo da reskilling al 60%")
    source_quality: str                  # "all_structured" | "partial_fallback" | "mostly_inferred"
                                         # → indica quanto il match è basato su dati certi vs inferiti


class ReskillingOutlook(BaseModel):
    """Investimento su percorso di reskilling."""
    active_paths: list[ReskillingPathSummary]
    relevant_to_jd: bool                 # almeno un path copre skill richieste dalla JD
    covers_missing_skills: list[str]     # quali skill mancanti sono coperte dal reskilling
    completion_forecast: str | None      # "completamento entro 2026-04-15"
    trajectory_score: float              # 0-1, quanto il reskilling copre i gap JD

class ReskillingPathSummary(BaseModel):
    course_name: str
    target_skills: list[str]
    completion_pct: int
    is_active: bool


class AvailabilityAssessment(BaseModel):
    """Assessment disponibilità rispetto alla JD."""
    status: str                          # free | partial | busy | unavailable
    allocation_pct: int
    current_project: str | None
    available_from: str | None
    available_to: str | None
    is_intercontratto: bool
    ic_sub_state: str | None             # ic_available | ic_in_reskilling | ic_in_transition
    fit_for_period: bool                 # se matcha il periodo richiesto dalla JD
    availability_note: str               # "disponibile da subito" | "libero dal 15/04" | "IC, bench"
```

### Cosa è implementabile per sprint

| Sezione | Sprint 10 | Sprint 11 | Sprint 12+ |
|---------|:---------:|:---------:|:----------:|
| `skill_levels.canonical` | ✅ SkillWeight + normalizer | — | — |
| `skill_levels.must_have` | ✅ match con JD skills | — | — |
| `skill_levels.nice_to_have` | ✅ se JD distingue required/preferred | — | — |
| `skill_levels.potential` | ⚠️ parziale (da chunk match) | ✅ con KP Builder | — |
| `consolidated` | ✅ SkillWeight con years ≥ 3 | — | — |
| `red_flags` | ⚠️ basic (seniority_mismatch, gap_in_must_have) | ✅ con KP completo | ✅ LLM assessment |
| `risk_opportunity` | ⚠️ `source_quality` (structured vs fallback) | ✅ con reskilling data | ✅ LLM risk analysis |
| `reskilling_investment` | ❌ richiede reskilling service | ✅ Sprint 11 | — |
| `availability` | ✅ già operativo + IC sub-state basic | ✅ con IC sub-state completo | — |

**Sprint 10 implementa:** `skill_levels` (canonical, must_have, nice_to_have), `consolidated`, `availability`, e versioni basic di `red_flags` (seniority_mismatch, gap_in_must_have) e `risk_opportunity` (source_quality).

**Sprint 11 completa:** `potential` con KP Builder, `reskilling_investment`, red_flags con dati reskilling.

**Sprint 12 arricchisce:** L'LLM con KP completo produce valutazioni qualitative profonde per red_flags e risk_opportunity.

### Response API aggiornata

```python
class SearchResponse(BaseModel):
    # --- Risultati per layer ---
    candidates_by_skills: list[ProfileMatch]
    candidates_by_chunks: list[ProfileMatch]
    candidates_fused: list[ProfileMatch] | None

    # --- Assessment strutturato per candidato ---
    assessments: dict[str, CandidateAssessment]  # chiave = cv_id

    # --- Metadata ricerca ---
    fallback_activated: bool
    recovered_skills: list[str] | None
    no_match_reason: str | None
    fusion_strategy: str | None
    search_metadata: SearchMetadata

class SearchMetadata(BaseModel):
    query_skills_raw: list[str]         # skill dalla JD prima della normalizzazione
    query_skills_normalized: list[str]  # skill dopo normalizzazione
    query_skills_recovered: list[str]   # skill dal fallback semantico (se attivato)
    layers_used: list[str]              # ["skill_search", "chunk_search", "skills_dictionary_fallback"]
    scoring_formula: str                # "weighted_v2" | "legacy_0.7_0.3"
    total_candidates_evaluated: int
    fusion_applied: bool
    elapsed_ms: int
```

---

## Definition of Done (Sprint-level)

- [ ] Tutte le issue hanno PR approvata e mergiata su `main`
- [ ] Test passano su CI (ruff + pytest)
- [ ] Coverage complessiva ≥ 80%
- [ ] SkillWeight model operativo con weighted scoring
- [ ] Seniority calcolata (non più "unknown")
- [ ] `skills_dictionary` collection in Qdrant con skill canoniche embeddate
- [ ] Fallback semantico operativo quando `normalized_skills == []`
- [ ] `cv_chunks` collection creata e integrata nel workflow
- [ ] Fusione risultati Layer 1 + Layer 2 con output separati
- [ ] Scoring formula evoluta (weighted + domain boost) con feature flag
- [ ] Nessuna regressione su pipeline stabilizzata (Sprint 9)
- [ ] Metriche Prometheus per fallback e fusione attive

---

## Metriche di Successo

| Metrica | Target | Baseline (pre-sprint) |
|---------|--------|-----------------------|
| SP completati | ≥ 13/16 (81%) | 0 |
| Seniority calcolata | 100% profili | 0% (sempre "unknown") |
| skills_dictionary entries | = skill canoniche nel YAML | 0 (collection non esiste) |
| cv_chunks indicizzati | 100% CV processati | 0 (collection non esiste) |
| Fallback activation rate | misurabile | N/A |
| Scoring formula | weighted + domain boost | flat 0.7/0.3 |
| Test coverage | ≥ 80% | ~65% (stima) |

---

## Rischi e Mitigazioni

| Rischio | Prob. | Impatto | Mitigazione |
|---------|:-----:|:-------:|-------------|
| Enhanced extraction prompt cambia output LLM | Media | Alto | Validation layer post-extraction (LLM-study §14 AP-1); test di regressione su CV campione |
| skills_dictionary troppo generica per JD complesse | Media | Medio | Tuning top-K e similarity threshold; monitorare `fallback_skill_recovery_empty_total` |
| Score normalization skill vs chunk non triviale | Media | Alto | RRF come default (rank-based, no normalizzazione); A/B test con weighted in Sprint 11 |
| cv_chunks aumenta tempo pipeline | Bassa | Medio | BestEffortChord; pipeline chunk non blocca skill embedding |
| Scoring formula update introduce regressione | Bassa | Alto | Feature flag `USE_WEIGHTED_SCORING` (default: off fino a benchmark Sprint 11) |
| Dizionario YAML cambia e skills_dictionary va out-of-sync | Bassa | Basso | Job di re-indexing automatico su cambio `dictionary_version`; CI check |

---

## Dipendenze Esterne

- **Sprint 9 completato** ✅ — Pipeline stabile, BestEffortChord, monitoring
- **Qdrant**: creazione 2 nuove collection (`skills_dictionary`, `cv_chunks`) — nessun upgrade, solo nuove collection
- **Embedding model**: stesso di `cv_skills` e `cv_experiences` — nessun cambio
- **Skill dictionary YAML**: deve essere stabile e versionato (è già versionato)
- **LLM provider**: prompt extraction aggiornato richiede compatibilità con modello in uso (GPT-4o/Ollama)
- **Alertmanager**: receiver Slack placeholder da Sprint 9 — issue follow-up separata

---

## Cosa NON è nello scope

| Item | Motivo | Sprint candidato |
|------|--------|:----------------:|
| Reskilling infrastructure completa (cache, service, task) | Solo schema in S10; il resto richiede consumo REST API dallo scraper | Sprint 11 |
| KP Builder service | Richiede reskilling service + `cv_chunks` + `SkillWeight` tutti operativi | Sprint 11 |
| KPContextBuilder (serializzazione KP → testo) | Dipende da KP Builder | Sprint 12 |
| Multi-scenario prompting (LLM-study §6) | Richiede KP Builder + Context Builder | Sprint 12-13 |
| Source Attribution | È parte integrante del KP model (`SkillDetail.source`, `RelevantChunk.source_collection`), non un'issue separata | Sprint 11 con KP |
| Cross-collection search (cv_experiences nel ranking) | Phase 2 Experience Layer (Arch §7.2) | Sprint 13 |
| cv_reskilling collection + trajectory scoring | Phase 3 (Arch §7.3) | Sprint 13-14 |
| Profile Statistics API (Arch §4.3) | Phase 4 | Sprint 15-16 |
| #17/#16 UI items | Sprint 5 Backlog | Futuro |
| #34 Benchmark search | Più significativo dopo scoring evoluto + fallback operativi | Sprint 11 |

---

## Mapping alla Roadmap

### Architecture Analysis §7 — Phase 1 Foundation

| Task | Effort doc | Sprint | Stato |
|------|:----------:|:------:|:-----:|
| Best-effort chord pattern | 3d | S9 | ✅ |
| SkillWeight model | 2d | **S10** | 🔜 |
| Enhanced LLM extraction prompt | 2d | **S10** | 🔜 |
| cv_skills payload evolution | 1d | **S10** | 🔜 |
| Scoring formula update | 2d | **S10** | 🔜 |
| Test suite | 2d | **S10** | 🔜 |

### LLM-study §13 — Fase 1 Fondamenta

| Task | Sprint | Stato |
|------|:------:|:-----:|
| Config.py: aggiungere campi LLM | **S10** | 🔜 |
| Seniority calculator | **S10** | 🔜 |
| Reskilling schemas + normalizer | **S10** (solo schema) | 🔜 |
| Reskilling cache + service (REST) | S11 | ⏳ |
| Reskilling Celery task integration | S11 | ⏳ |
| KnowledgeProfile schema | S11 | ⏳ |
| IC sub-state calculator | S11 | ⏳ |

---

## Planning Notes (risposte al team)

> Le seguenti note rispondono alle domande emerse nel planning meeting.

**Q1 — Allineamento alla visione TO-BE:**
Sì, Sprint 10 è il primo mattone operativo. La sezione "Visione Multi-Sprint" all'inizio del documento rende esplicito il legame.

**Q2 — Ordine dei mattoni:**
Confermato: SkillWeight + Seniority + cv_chunks + scoring (S10) → KP Builder + Reskilling infra (S11) → Context Builder + Multi-Scenario (S12). La retro-roadmap è nella sezione "Mapping alla Roadmap".

**Q3 — #63 come Layer 2 entry point:**
Sì, #63 è presentato come "primo caso d'uso del Layer 2 Hybrid Context", non come feature a sé. Vedi sezione "#63 come Layer 2 Entry Point".

**Q4 — Decisione A/B/C:**
**A + C** per coerenza architetturale. Opzione B scartata perché mescola fallback e retrieval nello stesso layer. Vedi tabella "Decisione architetturale".

**Q5 — Comunicazione roadmap vs delivery:**
Aggiunta sezione "Visione Multi-Sprint" con diagramma esplicito S10→S11→S12→S13-14→S15-18 e tabella "Capacità desiderata → Dove si costruisce".

**Q6 — Ownership & alignment:**
Le domande del backend hanno prodotto la decisione A+C. Nessun ulteriore allineamento necessario se il team conferma.

---

*Ultimo aggiornamento: 8 marzo 2026*
