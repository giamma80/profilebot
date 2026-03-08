# Sprint 10 — Risposta Tecnica al Team Backend

> **Data:** 9 marzo 2026
> **Da:** Giamma (Product Owner)
> **A:** Team Backend
> **Contesto:** Risposta all'analisi codebase ricevuta dal team. Include decisioni, conferme, priorità e tutti gli AC/schema necessari per iniziare lo sviluppo.

---

## TL;DR — Decisioni chiave

| # | Domanda del team | Decisione |
|---|------------------|-----------|
| 1 | Confermi che devo procedere su #63? | **Sì, confermato. #63 prima.** Ordine: #63 → #71 → #24 |
| 2 | Endpoint nuovo o aggiornare `/api/v1/search/skills`? | **Aggiornare l'endpoint esistente** con backward compatibility |
| 3 | Ordine proposto dal team | **Confermato** con una precisazione (vedi sotto) |

---

## 1. Conferma ordine di lavoro

L'ordine proposto dal team è **corretto e confermato**:

```
#63 (8 SP) → #71 (5 SP) → #24 (3 SP)
```

**Precisazione importante:** Dentro #63, le 3 fasi sono sequenziali:

1. **Fase 1** — Skill Recovery via `skills_dictionary` (Opz. A) — giorni 1-2
2. **Fase 2** — `cv_chunks` collection + chunk pipeline (Opz. C) — giorni 2-3
3. **Fase 3** — Ricerca parallela + Fusione + Response API — giorni 4-6

#71 (SkillWeight + Scoring composito) viene **dopo** #63 perché:
- La formula multi-layer in #71 ha bisogno dei risultati di Layer 1 + Layer 2 per comporre lo score
- Il weighted scoring è dietro feature flag (`scoring_use_weighted = False` di default) quindi è safe attivarlo dopo

#24 (Test Coverage) in parallelo o alla fine, come il team preferisce.

---

## 2. Endpoint: aggiornare l'esistente

**Decisione:** Aggiornare `/api/v1/search/skills` — **NON** creare un nuovo endpoint.

**Motivazione:** Il multi-layer search **sostituisce** il single-layer. Non sono due modalità alternative, è un'evoluzione.

**Backward compatibility garantita così:**

```python
# Il campo "results" rimane per backward compat
# I nuovi campi sono additivi (non rompono i client esistenti)

class SkillSearchResponse(BaseModel):
    # --- LEGACY (mantenuti per backward compat) ---
    results: list[ProfileMatch]          # = candidates_fused (o candidates_by_skills se fusion off)
    total: int
    limit: int
    offset: int
    query_time_ms: int

    # --- NUOVI CAMPI (Sprint 10) ---
    candidates_by_skills: list[ProfileMatch] | None = None   # Layer 1
    candidates_by_chunks: list[ProfileMatch] | None = None   # Layer 2
    candidates_fused: list[ProfileMatch] | None = None       # Fusione
    fallback_activated: bool = False
    recovered_skills: list[str] | None = None
    no_match_reason: str | None = None
    fusion_strategy: str | None = None                       # "rrf" | "weighted" | null
    search_metadata: SearchMetadata | None = None
```

- `results` = `candidates_fused` se fusione attiva, altrimenti `candidates_by_skills`
- I nuovi campi sono **tutti opzionali con default** → i client attuali non si rompono
- `extra = "forbid"` va cambiato in `extra = "ignore"` o rimosso sul response model

**File da modificare:** `src/api/v1/schemas.py`

---

## 3. Risposta punto per punto all'analisi del team

### 3.1 Stato #63 — Gap confermati e direttive

Il team ha identificato correttamente tutti i gap. Ecco le direttive specifiche:

#### Gap 1: `chunk_pipeline.py` non esiste

**Direttiva:** Creare `src/core/embedding/chunk_pipeline.py`

- **Base:** Riusare la logica di `EmbeddingPipeline._build_experience_points()` come template
- **Estendere a:** summary CV, education, certificazioni, testo generico
- **Payload minimo per ogni chunk:**
  ```python
  {
      "cv_id": str,
      "res_id": int,
      "section_type": str,      # "experience" | "education" | "summary" | "certification" | "generic"
      "chunk_index": int,
      "text_preview": str,      # primi 200 char
  }
  ```
- **ID deterministico:** `uuid5(NAMESPACE_URL, f"{cv_id}:chunk:{section_type}:{chunk_index}")`
- **Collection:** `cv_chunks` (schema già definito in `collections.py`)
- **Integrazione:** nel workflow post-refresh, chiamare `chunk_pipeline.process_cv()` dopo `EmbeddingPipeline.process_cv()`, idealmente via BestEffortChord per parallelismo

#### Gap 2: Fallback NON integrato in `search_by_skills()`

**Direttiva:** Modificare `src/services/search/skill_search.py` linea 108

```python
# PRIMA (attuale):
if not normalized_skills:
    raise ValueError("At least one valid skill is required")

# DOPO:
if not normalized_skills:
    if settings.search_fallback_enabled:
        from src.core.search.fallback import recover_skills_from_dictionary
        recovered = recover_skills_from_dictionary(
            query_text=" ".join(skills),  # JD originale
            top_k=5,
            score_threshold=0.7,
        )
        if recovered:
            logger.info(
                "FALLBACK_SKILL_RECOVERY via skills_dictionary: recovered %s",
                recovered,
            )
            normalized_skills = recovered
            fallback_activated = True
        else:
            logger.info(
                "FALLBACK_SKILL_RECOVERY: no skills recovered (threshold=0.7)"
            )
            return SkillSearchResponse(
                results=[],
                total=0,
                limit=limit,
                offset=offset,
                query_time_ms=...,
                no_match_reason="no_normalizable_skills_even_with_semantic_fallback",
                fallback_activated=True,
            )
    else:
        raise ValueError("At least one valid skill is required")
```

**Nota:** `settings.search_fallback_enabled` è già definito in `config.py` (default `True`) ma non viene mai usato.

#### Gap 3: Ricerca parallela NON implementata

**Direttiva:** Creare un orchestratore in `src/services/search/service.py` (nuovo file) o modificare `skill_search.py`

Flow:
```
1. skill_search = search_by_skills(normalized_skills, ...)    # Layer 1
2. chunk_search = search_by_chunks(query_text, ...)           # Layer 2 (parallelo)
3. fused = rrf_fuse(skill_search.results, chunk_search.results)  # Fusione
4. return MultiLayerSearchResponse(
       candidates_by_skills=skill_search.results,
       candidates_by_chunks=chunk_search.results,
       candidates_fused=fused,
       ...
   )
```

- `search_by_chunks()` in `chunk_search.py` **esiste già** e funziona
- `rrf_fuse()` in `fusion.py` **esiste già** e funziona
- Manca solo l'orchestrazione e il wiring

**Nota sul parallelismo:** Per Sprint 10, l'esecuzione sequenziale va bene (Layer 1 poi Layer 2). Il parallelismo via `asyncio` o thread è un'ottimizzazione futura. L'importante è che entrambi i layer vengano eseguiti.

#### Gap 4: Output separato non implementato

**Direttiva:** Il response model (vedi sezione 2 sopra) include `candidates_by_skills`, `candidates_by_chunks`, `candidates_fused` come campi separati.

#### Gap 5: Filtro idoneità non implementato

**Direttiva:** Post-fusione, applicare:
```python
def is_eligible(candidate: ProfileMatch, must_have_skills: set[str]) -> bool:
    has_must_have = bool(must_have_skills.intersection(candidate.matched_skills))
    match_ratio = len(candidate.matched_skills) / max(1, len(candidate.matched_skills) + len(candidate.missing_skills))
    return has_must_have or match_ratio >= 0.4
```

- Se nessun candidato passa → `no_match_reason = "below_eligibility_threshold"`
- Il filtro si applica su `candidates_fused` (o `candidates_by_skills` se fusione off)

#### Gap 6: Metriche Prometheus non implementate

**Direttiva:** 3 counter:
```python
from prometheus_client import Counter

FALLBACK_ACTIVATED = Counter("search_fallback_activated_total", "Fallback activations")
CHUNK_RESULTS = Counter("search_chunk_results_count", "Chunk search results returned")
FUSION_USED = Counter("search_fusion_used_total", "Fusion strategy activations")
```

Incrementare nei punti appropriati del flow di orchestrazione.

---

### 3.2 Stato #71 — Gap confermati e direttive

#### Gap 1: SkillWeight usa valori hardcoded

**Confermato.** In `pipeline.py` linee 167-176:
```python
SkillWeight(
    name=skill.canonical,
    years=0.0,           # HARDCODED ← da estrarre dal CV
    level="intermediate", # HARDCODED ← da estrarre dal CV
    certified=False,      # HARDCODED ← da estrarre dal CV
    from_experience=True,
)
```

**Direttiva Sprint 10:**
- Aggiornare il prompt LLM di extraction per estrarre `years`, `level`, `certified` per ogni skill
- Passare i dati estratti al costruttore `SkillWeight`
- Formula peso: `weight = 1.0 + log(1 + years) + (0.5 if certified else 0)`
- **Se il prompt LLM non riesce ad estrarre** (graceful degradation): usare i default attuali come fallback

#### Gap 2: W_skill, W_exp, W_resk mancanti in config

**Direttiva:** Aggiungere a `config.py`:
```python
# Multi-layer scoring weights
search_weight_skill: float = Field(default=0.7, validation_alias="SEARCH_WEIGHT_SKILL")
search_weight_chunk: float = Field(default=0.3, validation_alias="SEARCH_WEIGHT_CHUNK")
# W_resk non serve ancora (Sprint 13)
```

**Nota:** `search_chunk_weight: float = 0.3` **esiste già** in config.py ma non viene usato. Potete riusarlo direttamente come `W_chunk` nella fusione weighted.

#### Gap 3: Scoring composito multi-layer

**Direttiva:** La formula target è:
```
final_score = W_skill * score_Layer1 + W_chunk * score_Layer2
```
dove:
- `score_Layer1 = weighted_skill_score + domain_boost - seniority_penalty` (già in `calculate_weighted_final_score`)
- `score_Layer2 = cosine_similarity` dal chunk search
- `W_skill = 0.7`, `W_chunk = 0.3` (default, configurabili)

Questo è essenzialmente quello che fa `weighted_fuse()` in `fusion.py` — va solo wired.

#### Gap 4: Seniority

**Nota positiva:** La seniority **è già implementata correttamente** (`calculate_seniority_bucket` in `src/core/seniority/calculator.py`). Il team può verificare che venga usata nel payload `cv_skills`. Dalle mie verifiche, pipeline.py linee 159-165 la calcolano correttamente. Il gap precedente ("always unknown") era pre-Sprint 9 ed è già risolto.

---

### 3.3 Stato #24 — Test Coverage

Il team ha identificato correttamente i gap. Focus su:

| Modulo | Priorità | Cosa testare |
|--------|:--------:|-------------|
| `core/search/fallback.py` | P0 | Recovery con skill valide, JD vuota, threshold, domain_filter |
| `core/search/fusion.py` | P0 | RRF con overlap, senza overlap, liste vuote, ordine |
| `services/search/chunk_search.py` | P0 | Query vuota, risultati vuoti, filtri availability |
| `core/embedding/chunk_pipeline.py` | P0 | Process CV, sezioni multiple, testi vuoti |
| `services/search/skill_search.py` | P0 | Fallback integration, no_match_reason, backward compat |
| `services/search/scoring.py` | P1 | Weighted scoring, domain_boost, seniority_penalty |
| `tasks/` | P1 | BestEffortChord con chunk pipeline |

Target: **≥ 80% complessivo, nessun modulo critico sotto 70%**.

---

## 4. Schema completi (copia da SPRINT10_COMMITMENT.md)

Il team ha segnalato che GitHub MCP non è disponibile. Di seguito tutti gli schema necessari.

### 4.1 SearchResponse target (Sprint 10)

```python
class SearchResponse(BaseModel):
    # --- Risultati per layer ---
    candidates_by_skills: list[ProfileMatch]
    candidates_by_chunks: list[ProfileMatch]
    candidates_fused: list[ProfileMatch] | None

    # --- Assessment strutturato per candidato (parziale in S10) ---
    assessments: dict[str, CandidateAssessment] | None = None  # chiave = cv_id

    # --- Metadata ricerca ---
    fallback_activated: bool
    recovered_skills: list[str] | None
    no_match_reason: str | None
    fusion_strategy: str | None
    search_metadata: SearchMetadata

    # --- Backward compat ---
    results: list[ProfileMatch]     # = candidates_fused o candidates_by_skills
    total: int
    limit: int
    offset: int
    query_time_ms: int


class SearchMetadata(BaseModel):
    query_skills_raw: list[str]
    query_skills_normalized: list[str]
    query_skills_recovered: list[str]       # dal fallback semantico
    layers_used: list[str]                  # ["skill_search", "chunk_search", "skills_dictionary_fallback"]
    scoring_formula: str                    # "weighted_v2" | "legacy_0.7_0.3"
    total_candidates_evaluated: int
    fusion_applied: bool
    elapsed_ms: int
```

### 4.2 CandidateAssessment (target TO-BE, parziale in S10)

```python
class CandidateAssessment(BaseModel):
    skill_levels: SkillLevelsBreakdown
    consolidated: list[ConsolidatedSkill]
    red_flags: list[RedFlag]
    risk_opportunity: RiskAssessment
    reskilling_investment: ReskillingOutlook | None     # None in S10
    availability: AvailabilityAssessment


class SkillLevelsBreakdown(BaseModel):
    canonical: list[SkillMatch]
    must_have: list[SkillMatch]
    nice_to_have: list[SkillMatch]
    potential: list[PotentialSkill]
    unknown_in_jd: list[str]
    coverage_pct: float


class SkillMatch(BaseModel):
    name: str
    domain: str
    level: str                  # junior|intermediate|senior|expert
    years: float | None
    certified: bool
    weight: float               # SkillWeight calcolato
    match_confidence: float     # 0-1
    match_type: str             # exact|alias|fuzzy|semantic_fallback


class PotentialSkill(BaseModel):
    name: str
    source: str                 # "chunk_match" | "experience_inference" | "reskilling"
    confidence: float
    evidence: str


class ConsolidatedSkill(BaseModel):
    name: str
    years: float                # >= 3 per qualificarsi
    certified: bool
    from_experience: bool
    weight: float
    consolidation_level: str    # "master" (>=8y) | "solid" (>=5y) | "established" (>=3y)


class RedFlag(BaseModel):
    type: str                   # seniority_mismatch | skill_decay | availability_risk
                                # | low_confidence_match | overqualified | ic_in_transition
                                # | gap_in_must_have | stale_reskilling
    severity: str               # high | medium | low
    description: str
    affected_skills: list[str] | None


class RiskAssessment(BaseModel):
    risk_level: str             # low | medium | high
    risk_factors: list[str]
    opportunity_factors: list[str]
    azzardo_note: str | None
    source_quality: str         # "all_structured" | "partial_fallback" | "mostly_inferred"


class ReskillingOutlook(BaseModel):
    active_paths: list[ReskillingPathSummary]
    relevant_to_jd: bool
    covers_missing_skills: list[str]
    completion_forecast: str | None
    trajectory_score: float


class ReskillingPathSummary(BaseModel):
    course_name: str
    target_skills: list[str]
    completion_pct: int
    is_active: bool


class AvailabilityAssessment(BaseModel):
    status: str                 # free | partial | busy | unavailable
    allocation_pct: int
    current_project: str | None
    available_from: str | None
    available_to: str | None
    is_intercontratto: bool
    ic_sub_state: str | None    # ic_available | ic_in_reskilling | ic_in_transition
    fit_for_period: bool
    availability_note: str
```

**Cosa implementare in Sprint 10:**
- `skill_levels` (canonical, must_have, nice_to_have) ✅
- `consolidated` ✅
- `availability` ✅
- `red_flags` basic (seniority_mismatch, gap_in_must_have) ⚠️
- `risk_opportunity` (solo source_quality) ⚠️
- `reskilling_investment` = `None` ❌ (Sprint 11)
- `potential` parziale (da chunk match) ⚠️

### 4.3 SkillWeight model

```python
class SkillWeight(BaseModel):
    name: str                       # Skill normalizzata
    years: float = 0.0              # Anni di esperienza sulla skill
    level: str = "intermediate"     # junior|intermediate|senior|expert
    certified: bool = False         # Ha certificazione sulla skill
    from_experience: bool = True    # Skill verificata da esperienza
    weight: float                   # = 1.0 + log(1 + years) + (0.5 if certified else 0)
```

**File:** `src/core/skills/weight.py` (già esiste, verificare formula)

### 4.4 Collection schemas

**`skills_dictionary`** (schema già in `collections.py`):
```
Payload: {
    canonical_name: str,
    domain: str,
    aliases_count: int,
    related_skills: list[str]
}
```

**`cv_chunks`** (schema già in `collections.py`):
```
Payload: {
    cv_id: str,
    res_id: int,
    section_type: str,      # experience|education|summary|certification|generic
    chunk_index: int,
    text_preview: str
}
```

---

## 5. Acceptance Criteria completi

### #63 — Fallback semantico + Layer 2 (8 SP)

- [ ] Collection `skills_dictionary` creata con embedding di tutte le skill canoniche
- [ ] Fallback attivato quando `normalized_skills == []`
- [ ] Logging esplicito: `"FALLBACK_SKILL_RECOVERY via skills_dictionary: recovered [%s]"`
- [ ] Almeno 1 skill canonica per JD generiche
- [ ] Collection `cv_chunks` creata e popolata dal workflow (chunk_pipeline.py)
- [ ] Ricerca parallela Layer 1 + Layer 2
- [ ] Strategia di fusione implementata (RRF default, weighted configurabile)
- [ ] Non regressione: se skill già valide, Layer 2 è complementare (non sostitutivo)
- [ ] `no_match_reason` se nessun match: `"no_normalizable_skills_even_with_semantic_fallback"` o `"below_eligibility_threshold"`
- [ ] Filtro idoneità: 1 must-have matchata OR `match_ratio >= 0.4`
- [ ] Output separato: `candidates_by_skills`, `candidates_by_chunks`, `candidates_fused`
- [ ] Endpoint `/api/v1/search/skills` aggiornato con nuovi campi (backward compat)
- [ ] Metriche Prometheus: `search_fallback_activated_total`, `search_chunk_results_count`, `search_fusion_used_total`
- [ ] ≥ 10 test (skill dictionary indexing, fallback recovery, chunk indexing, fusione, filtro, no_match_reason, non-regressione)

### #71 — SkillWeight + Seniority + Scoring evoluto (5 SP)

- [ ] `SkillWeight` model con calcolo peso automatico (`1.0 + log(1+years) + cert_bonus`)
- [ ] Prompt LLM extraction aggiornato per estrarre years/level/certified
- [ ] Seniority calcolata per ogni profilo (verificare che non sia più "unknown")
- [ ] `cv_skills` payload include `weighted_skills` con dati reali (non hardcoded)
- [ ] Config.py con `search_weight_skill`, `search_weight_chunk`
- [ ] Scoring formula evoluta: `W_skill * weighted_skill_score + domain_boost - seniority_penalty`
- [ ] Feature flag `scoring_use_weighted` per rollback sicuro (default: off)
- [ ] ≥ 8 test (SkillWeight, seniority, scoring, backward compatibility)

### #24 — Test Coverage (3 SP)

- [ ] Coverage complessiva ≥ 80%
- [ ] Nessun modulo critico sotto 70%
- [ ] CI coverage gate attivo
- [ ] Report coverage HTML come CI artifact

---

## 6. File map — cosa esiste, cosa creare, cosa modificare

| File | Stato | Azione Sprint 10 |
|------|:-----:|-------------------|
| `src/core/search/fallback.py` | ✅ Esiste | **Integrare** in `skill_search.py` |
| `src/core/search/fusion.py` | ✅ Esiste | **Importare** nel service orchestrator |
| `src/services/search/chunk_search.py` | ✅ Esiste | **Integrare** nel service orchestrator |
| `src/core/search/skill_dictionary_index.py` | ✅ Esiste | Verificare, usare per popolare collection |
| `src/services/qdrant/collections.py` | ✅ Esiste | Verificare schema `cv_chunks` e `skills_dictionary` |
| `src/core/skills/weight.py` | ✅ Esiste | **Verificare** formula peso, rimuovere hardcoded |
| `src/core/seniority/calculator.py` | ✅ Esiste | Verificare (dovrebbe essere già OK) |
| `src/services/search/scoring.py` | ✅ Esiste | **Estendere** con multi-layer scoring |
| `src/core/config.py` | ✅ Esiste | **Aggiungere** `search_weight_skill`, `search_weight_chunk` |
| `src/api/v1/schemas.py` | ✅ Esiste | **Estendere** con nuovi campi response |
| `src/core/embedding/pipeline.py` | ✅ Esiste | **Fix** SkillWeight hardcoded (linee 167-176) |
| `src/core/embedding/chunk_pipeline.py` | ❌ Non esiste | **CREARE** — chunk embedding pipeline |
| `src/services/search/service.py` | ❌ Non esiste | **CREARE** — orchestratore multi-layer |
| `src/api/v1/schemas.py` (assessment models) | ❌ Non esiste | **CREARE** o estendere — CandidateAssessment & co. |

---

## 7. Riepilogo valori e threshold

| Parametro | Valore | Dove |
|-----------|--------|------|
| RRF k constant | 60 | `fusion.py` (già implementato) |
| Fallback top_k | 5 | `fallback.py` (già implementato) |
| Fallback score_threshold | 0.7 | `fallback.py` (già implementato) |
| W_skill (default) | 0.7 | `config.py` → `search_weight_skill` |
| W_chunk (default) | 0.3 | `config.py` → `search_chunk_weight` (già esiste) |
| Domain boost | 1.2 | `skill_search.py` → `_calculate_domain_boost` (già implementato) |
| Seniority penalty | `abs(q - p) * 0.05` | `skill_search.py` → `_calculate_seniority_penalty` (già implementato) |
| Eligibility threshold | `match_ratio >= 0.4` | Da implementare nel service orchestrator |
| Feature flag scoring | `scoring_use_weighted` | `config.py` (già esiste, default `False`) |
| Feature flag fallback | `search_fallback_enabled` | `config.py` (già esiste, default `True`) |

---

## 8. Note finali

### Building blocks pronti al ~90%

L'analisi del team è accurata: i building block esistono quasi tutti a livello di funzione. Il gap principale è l'**orchestration layer** che li connette nel flusso di ricerca principale. Sprint 10 è essenzialmente un lavoro di **integration & wiring** più che di scrittura da zero.

### Cosa NON fare in Sprint 10

- NON implementare `reskilling_investment` (Sprint 11)
- NON implementare cross-collection search su `cv_experiences` (Sprint 13)
- NON fare A/B test sulla scoring formula (Sprint 11, con benchmark #34)
- NON parallelizzare Layer 1 + Layer 2 con asyncio (ottimizzazione futura)

### Domande aperte per il team

Se emergono dubbi durante lo sviluppo, le priorità sono:
1. **Backward compat** — I client attuali non devono rompersi
2. **Non regressione** — Se skill valide, il comportamento attuale è preservato
3. **Graceful degradation** — Se un layer fallisce, gli altri continuano

Buon lavoro. Procedi pure con #63 Fase 1.

---

*Documento generato il 9 marzo 2026*
