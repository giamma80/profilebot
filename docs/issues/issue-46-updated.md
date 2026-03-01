# [US-009.3] KP Schema e Builder Base

> **Story Points:** 5 | **Branch:** `feature/US-009.3-kp-builder` | **Sprint:** 6

## Obiettivo

Creare il modello `KnowledgeProfile` unificato che assembla dati da 4 sorgenti (Qdrant, AvailabilityService, ReskillingService, SkillDictionary) e lo serializza come contesto strutturato per il prompt LLM.

## Dipendenze

| Dipendenza | Stato | Note |
|-----------|-------|------|
| **US-009.1** Seniority Calculator | ✅ Done | `src/core/seniority/calculator.py` disponibile su `main` |
| **US-009.2** Reskilling Infrastructure | ✅ Done | `src/services/reskilling/` completo: schemas, normalizer, cache, service |
| **Skill Dictionary v2** | ✅ Done | `data/skills_dictionary.yaml` v2.0.0 — 1210 skill, 786 alias, 22 domini |

Tutte le dipendenze sono soddisfatte. **Non servono mock/stub** — il Builder può usare i servizi reali.

---

## Architettura

```
                    KPBuilder.build(res_id, cv_id, query_skills)
                         │
         ┌───────────────┼───────────────┐───────────────┐
         ▼               ▼               ▼               ▼
   Qdrant payload   Availability    Reskilling      SkillDictionary
   (skills, exp,    Service.get()   Service.get()   (domain, alias,
    metadata)                                        certifications)
         │               │               │               │
         ▼               ▼               ▼               ▼
      SkillDetail[]   Availability   ReskillingPath[]  arricchimento
      Experience[]    Detail         ICSubState        dominio/certs
         │               │               │               │
         └───────────────┴───────────────┴───────────────┘
                                │
                     KnowledgeProfile (Pydantic v2)
                                │
                     KPContextSerializer.serialize(kp, scenario)
                                │
                     str (testo strutturato per prompt LLM)
                                │
                     estimate_tokens(text) → int
```

**Pattern chiave: Graceful Degradation** — se una sorgente fallisce, il KP si costruisce comunque con i dati disponibili (try/except + logging.warning per ogni sorgente).

---

## File coinvolti

### Da creare

| File | Contenuto |
|------|-----------|
| `src/core/knowledge_profile/__init__.py` | Export pubblici |
| `src/core/knowledge_profile/schemas.py` | `KnowledgeProfile` + sotto-modelli |
| `src/core/knowledge_profile/ic_sub_state.py` | `ICSubStateCalculator` |
| `src/core/knowledge_profile/builder.py` | `KPBuilder` service |
| `src/core/knowledge_profile/serializer.py` | `KPContextSerializer` + `estimate_tokens()` |
| `tests/core/knowledge_profile/test_schemas.py` | Test schema |
| `tests/core/knowledge_profile/test_ic_sub_state.py` | Test IC sub-state |
| `tests/core/knowledge_profile/test_builder.py` | Test builder con mock |
| `tests/core/knowledge_profile/test_serializer.py` | Test serializer |

### Da leggere (riferimento)

| File | Motivo |
|------|--------|
| `docs/LLM-study.md` §3 (KP model), §7 (IC sub-state), §9 (Context Builder), §10 (Token budget) | Design spec |
| `src/services/availability/schemas.py` | `ProfileAvailability`, `AvailabilityStatus` |
| `src/services/reskilling/schemas.py` | `ReskillingRecord`, `ReskillingStatus` |
| `src/core/seniority/calculator.py` | `calculate_seniority_bucket()`, `SeniorityBucket` |
| `src/core/skills/schemas.py` | `NormalizedSkill`, `SkillExtractionResult` |
| `src/core/parser/schemas.py` | `ParsedCV`, `ExperienceItem`, `CVMetadata` |

---

## Indicazioni implementative dettagliate

### 1. `schemas.py` — KnowledgeProfile

Lo schema del LLM-study §3.2 va **adattato ai tipi reali** del codebase. Delta importanti:

| Design Doc (§3.2) | Codice Reale | Azione |
|-------------------|-------------|--------|
| `ReskillingPath.target_skills: list[str]` | `ReskillingRecord.skill_target: str \| None` | Wrappare in lista: `[r.skill_target] if r.skill_target else []` |
| `ReskillingStatus: ACTIVE/COMPLETED/DROPPED` | `ReskillingStatus: IN_PROGRESS/COMPLETED/PLANNED` | Usare i valori reali. `is_active` → `status == IN_PROGRESS` |
| `SkillDetail.related_certifications: list[str]` | `SkillEntry.certifications: list[str]` (dal dictionary) | Mappare da `SkillEntry` |
| `AvailabilityDetail.ic_sub_state` | Non esiste nell'availability schema | Calcolato dall'`ICSubStateCalculator`, field nel KP |

Sotto-modelli da definire:

```python
class SkillDetail(BaseModel):
    canonical: str
    domain: str
    confidence: float = Field(ge=0.0, le=1.0)
    match_type: Literal["exact", "alias", "fuzzy"]
    source: Literal["cv", "reskilling"] = "cv"
    reskilling_completion_pct: int | None = None
    related_certifications: list[str] = Field(default_factory=list)
    last_used_hint: str | None = None
    model_config = {"extra": "forbid"}

class AvailabilityDetail(BaseModel):
    status: AvailabilityStatus
    allocation_pct: int = Field(ge=0, le=100)
    current_project: str | None = None
    available_from: date | None = None
    available_to: date | None = None
    manager_name: str | None = None
    is_intercontratto: bool
    model_config = {"extra": "forbid"}

class ReskillingPath(BaseModel):
    course_name: str
    target_skills: list[str]           # wrappato da skill_target singolo
    completion_pct: int | None = Field(default=None, ge=0, le=100)
    provider: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool                     # status == IN_PROGRESS
    model_config = {"extra": "forbid"}

class ExperienceSnapshot(BaseModel):
    company: str | None = None
    role: str | None = None
    period: str                         # "2020-2023" o "2023-presente"
    description_summary: str = ""       # max 200 chars
    related_skills: list[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}

class RelevantChunk(BaseModel):
    text: str
    source_collection: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    section_type: str | None = None
    model_config = {"extra": "forbid"}

class ICSubState(StrEnum):
    IC_AVAILABLE = "ic_available"
    IC_IN_RESKILLING = "ic_in_reskilling"
    IC_IN_TRANSITION = "ic_in_transition"

class KnowledgeProfile(BaseModel):
    cv_id: str
    res_id: int
    full_name: str | None = None
    current_role: str | None = None

    # Skill layer
    skills: list[SkillDetail]
    skill_domains: dict[str, int]       # {domain: count}
    total_skills: int
    unknown_skills: list[str] = Field(default_factory=list)

    # Seniority
    seniority_bucket: SeniorityBucket
    years_experience_estimate: int | None = None

    # Availability
    availability: AvailabilityDetail | None = None

    # IC sub-state (calcolato)
    ic_sub_state: ICSubState | None = None

    # Reskilling
    reskilling_paths: list[ReskillingPath] = Field(default_factory=list)
    has_active_reskilling: bool = False

    # Experiences
    experiences: list[ExperienceSnapshot] = Field(default_factory=list)

    # Chunks (opzionale, hybrid context)
    relevant_chunks: list[RelevantChunk] = Field(default_factory=list)

    # Matching metadata
    match_score: float = 0.0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    match_ratio: float = 0.0

    model_config = {"extra": "forbid"}
```

### 2. `ic_sub_state.py` — ICSubStateCalculator

Logica da LLM-study §7.2, adattata ai tipi reali:

```python
def calculate_ic_sub_state(
    availability: ProfileAvailability | None,
    reskilling_records: list[ReskillingRecord],
    *,
    is_in_transition: bool = False,
) -> ICSubState | None:
    if availability is None:
        return None
    if availability.allocation_pct > 0:
        return None
    if availability.status not in (AvailabilityStatus.FREE, AvailabilityStatus.UNAVAILABLE):
        return None

    # Priorità: transition > reskilling > available
    if is_in_transition:
        return ICSubState.IC_IN_TRANSITION

    active = [r for r in reskilling_records if r.status == ReskillingStatus.IN_PROGRESS]
    if active:
        return ICSubState.IC_IN_RESKILLING

    return ICSubState.IC_AVAILABLE
```

### 3. `builder.py` — KPBuilder

**Design pattern:** Constructor injection con Protocol per ogni sorgente. Ogni sorgente è opzionale nel `build()`.

```python
class KPBuilder:
    def __init__(
        self,
        availability_service: AvailabilityService,
        reskilling_service: ReskillingService,
        skill_dictionary: SkillDictionary,
    ) -> None: ...

    def build(
        self,
        *,
        cv_id: str,
        res_id: int,
        parsed_cv: ParsedCV,
        skill_result: SkillExtractionResult,
        query_skills: list[str] | None = None,
        match_score: float = 0.0,
    ) -> KnowledgeProfile:
        # 1. Identity + seniority (dal ParsedCV)
        # 2. Skills (da SkillExtractionResult + SkillDictionary enrichment)
        # 3. Availability (try/except → None se fallisce)
        # 4. Reskilling (try/except → [] se fallisce)
        # 5. IC sub-state (calcolato da availability + reskilling)
        # 6. Experiences (da ParsedCV.experiences → ExperienceSnapshot)
        # 7. Matching metadata (matched/missing vs query_skills)
        ...
```

**Graceful degradation:** ogni blocco sorgente è in try/except con `logger.warning("Failed to fetch X for res_id=%s: %s", res_id, exc)`.

### 4. `serializer.py` — KPContextSerializer

Segue il template di LLM-study §9.2. Parametri di troncamento configurabili:

```python
class KPContextSerializer:
    def __init__(
        self,
        max_skills_per_domain: int = 10,
        max_experiences: int = 3,
        max_chunks: int = 3,
        max_chunk_chars: int = 300,
    ) -> None: ...

    def serialize(self, kp: KnowledgeProfile) -> str:
        """Serializza un KP in testo strutturato per il prompt LLM."""
        ...

    def serialize_batch(
        self, profiles: list[KnowledgeProfile], scenario: str = "matching"
    ) -> str:
        """Serializza più KP con header candidato N/totale."""
        ...

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Stima token ≈ len(text) / 4."""
        return len(text) // 4
```

---

## Acceptance Criteria

- [ ] Schema Pydantic `KnowledgeProfile` + sotto-modelli (`SkillDetail`, `AvailabilityDetail`, `ReskillingPath`, `ExperienceSnapshot`, `RelevantChunk`, `ICSubState`)
- [ ] `ICSubStateCalculator` con logica: `not_ic` / `ic_available` / `ic_in_reskilling` / `ic_in_transition`
- [ ] `KPBuilder` assembla KP dalle 4 sorgenti con graceful degradation
- [ ] `KPContextSerializer` produce output testo strutturato per prompt LLM (formato §9.2)
- [ ] `estimate_tokens()` implementato (`len(text) // 4`)
- [ ] Graceful degradation: se una sorgente fallisce, il KP si costruisce con i dati disponibili
- [ ] 80%+ coverage sui nuovi moduli
- [ ] ≥ 8 test case (IC sub-state, builder, serializer)

---

## Test richiesti (≥ 8)

### IC Sub-State (4 test)
1. `test_not_ic_when_allocation_positive` — allocation_pct > 0 → `None`
2. `test_ic_available` — allocation 0, status FREE, no reskilling → `ic_available`
3. `test_ic_in_reskilling` — allocation 0, status FREE, reskilling IN_PROGRESS → `ic_in_reskilling`
4. `test_ic_in_transition_priority` — is_in_transition=True prevale su reskilling attivo → `ic_in_transition`

### Builder (3 test)
5. `test_build_complete_kp` — tutte le sorgenti disponibili → KP completo con tutti i campi
6. `test_graceful_degradation_availability_fails` — AvailabilityService raise → KP con `availability=None`, no crash
7. `test_build_with_minimal_input` — solo ParsedCV + SkillExtractionResult, nessun dato availability/reskilling → KP valido con campi opzionali vuoti

### Serializer (2 test)
8. `test_serialize_contains_expected_sections` — output contiene "SKILL MATCHATE", "DISPONIBILITÀ", header candidato
9. `test_estimate_tokens_consistent` — `estimate_tokens("a" * 400)` → 100

---

## Settings

Nessun nuovo setting richiesto. Il builder usa i servizi esistenti che hanno già i propri settings.

---

## DoD (Definition of Done)

- [ ] `ruff check` + `ruff format` passano
- [ ] `pytest` passa (tutti i test)
- [ ] Coverage ≥ 80% su `src/core/knowledge_profile/`
- [ ] Docstring su classi e metodi pubblici
- [ ] `from __future__ import annotations` in testa a ogni file
- [ ] `model_config = {"extra": "forbid"}` su tutti i BaseModel
- [ ] PR approvata e mergiata su `main`

---

## ⚠️ Attenzione — Delta Design Doc vs Codice Reale

Il design doc (`docs/LLM-study.md` §3.2) è stato scritto **prima** dell'implementazione di US-009.2. Ci sono differenze tra lo schema proposto e i tipi reali:

| Punto | Design Doc | Codice Reale | Come gestire |
|-------|-----------|-------------|-------------|
| Reskilling target | `target_skills: list[str]` | `skill_target: str \| None` | Nel builder: `[r.skill_target] if r.skill_target else []` |
| Reskilling status | `ACTIVE / COMPLETED / DROPPED` | `IN_PROGRESS / COMPLETED / PLANNED` | `is_active = (status == IN_PROGRESS)` |
| IC sub-state position | Campo di `AvailabilityDetail` | Campo separato nel KP top-level | `KnowledgeProfile.ic_sub_state: ICSubState \| None` |
| Seniority bucket | Tipo inline | `SeniorityBucket` da `src/core/seniority/calculator.py` | Import e riuso del type alias esistente |
| Skill dictionary | `get_domain(skill_name)` | `get_by_canonical(name) → SkillEntry` | Accedere a `entry.domain`, `entry.certifications` |

**Il codice reale ha la precedenza.** Lo schema KP deve allinearsi ai Pydantic model implementati, non al design doc.

---

## Ref

- `docs/LLM-study.md` §3 (KP model), §7 (IC), §9 (Context Builder), §10 (Token budget)
- `docs/SPRINT6_COMMITMENT.md` — Sprint goal e sequenza
- `docs/SPRINT6_DEV_GUIDE.md` §4 US-009.3 — Indicazioni implementative
