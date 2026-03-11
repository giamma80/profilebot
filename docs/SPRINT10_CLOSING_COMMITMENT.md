# Sprint 10 — Closing Commitment

> **Data:** 9 marzo 2026
> **Branch base:** `master` (post-merge PR #72)
> **Issue completata:** #63 ✅ (100% AC)
> **Issue rimanenti:** #71 (87.5%), #24 (25%)
> **Deadline Sprint:** 22 marzo 2026

---

## Stato attuale post-merge #63

| Issue | Completamento | Gap |
|-------|:---:|------|
| **#63** Semantic Fallback + Multi-Layer | ✅ 100% | Chiusa — tutti i 14 AC soddisfatti |
| **#71** SkillWeight + Scoring | 87.5% | AC2: `years=0.0` hardcoded, manca enricher |
| **#24** Test Coverage | 25% | Manca CI gate, threshold, HTML report |

---

## Step 1 — #71 AC2: Skill Enricher (branch: `feature/71-skill-enricher`)

### Problema
Il modello `SkillWeight` esiste ed è funzionante, ma `pipeline.py` lo crea con valori hardcoded:
```python
SkillWeight(name=skill.canonical, years=0.0, level="intermediate", certified=False)
```

### Soluzione: Enricher euristico (no LLM)
Creare `src/core/skills/enricher.py` che estrae metadata dalle sezioni CV già parsate:

```python
def enrich_skill_metadata(
    skill_name: str,
    experiences: list[dict],      # from CV parser
    certifications: list[str],    # from CV parser
) -> dict:
    """
    Returns: {"years": float, "level": str, "certified": bool}
    """
    years = _estimate_years_for_skill(skill_name, experiences)
    certified = _check_certification(skill_name, certifications)
    level = _infer_level(years)  # junior<2, mid 2-5, senior>5
    return {"years": years, "level": level, "certified": certified}
```

**Logica:**
- `_estimate_years_for_skill()`: Cerca skill_name nelle description delle esperienze, calcola delta date (end - start). Se skill presente in N esperienze, somma i periodi.
- `_check_certification()`: Fuzzy match tra skill_name e lista certifications (es. "AWS" matchato con "AWS Solutions Architect").
- `_infer_level()`: `years < 2` → junior, `2 ≤ years ≤ 5` → intermediate, `years > 5` → senior, `years > 10` → expert.

**Decisione chiave:** Sprint 10 usa euristica, non LLM. Copre ~80% dei casi. LLM enrichment → Sprint 11.

### File da creare/modificare
| File | Azione |
|------|--------|
| `src/core/skills/enricher.py` | **Nuovo** — funzioni di enrichment |
| `src/core/embedding/pipeline.py` | **Modifica** — sostituire hardcoded con chiamata enricher |
| `tests/test_skill_enricher.py` | **Nuovo** — test per enricher (≥5 test cases) |

### AC da chiudere
- [x] AC2: skill metadata estratta da esperienze/certificazioni CV (euristica)

### Stima: 2-3 giorni

---

## Step 2 — #24: CI Coverage Gate (branch: `feature/24-coverage-gate`)

### Problema
CI (`ci.yml`) genera coverage XML e lo uploada a Codecov, ma:
- Nessun threshold enforcement (`--cov-fail-under` assente)
- Nessun HTML report come artifact
- Non si sa quali moduli sono sotto il 70%

### Soluzione

#### 2A — CI gate (linea 102 di ci.yml)
```yaml
# PRIMA:
run: uv run pytest tests/ -v --cov=src --cov-report=xml

# DOPO:
run: uv run pytest tests/ -v --cov=src --cov-report=xml --cov-report=html --cov-fail-under=80
```

#### 2B — HTML report come artifact
```yaml
- name: Upload HTML coverage report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: coverage-html
    path: htmlcov/
    retention-days: 14
```

#### 2C — Baseline coverage + test gap analysis
1. Eseguire `pytest --cov=src --cov-report=term-missing` localmente
2. Identificare moduli sotto 70%
3. Aggiungere test mirati per i moduli critici

### File da creare/modificare
| File | Azione |
|------|--------|
| `.github/workflows/ci.yml` | **Modifica** — aggiungere fail-under + html + artifact |
| `tests/test_*.py` (vari) | **Nuovo/Modifica** — test per moduli sotto 70% |

### AC da chiudere
- [ ] AC2: CI gate `--cov-fail-under=80`
- [ ] AC3: Moduli sotto 70% coperti
- [ ] AC4: HTML coverage report come CI artifact

### Stima: 1-2 giorni

---

## Timeline

```
Giorno 1-2  │ Step 1: enricher.py + wiring pipeline + test
Giorno 3    │ Step 1: PR + merge #71
Giorno 3-4  │ Step 2: CI gate + coverage analysis + test gap
Giorno 4    │ Step 2: PR + merge #24
Giorno 4    │ Sprint 10 Review & chiusura milestone
```

---

## Branch Strategy

```
master ─────────────────────────────────────────────────►
  │
  ├── feature/71-skill-enricher ──── PR ──── merge ──►
  │                                            │
  └── feature/24-coverage-gate ───────── PR ── merge ►
```

---

## Rischi e mitigazioni

| Rischio | Probabilità | Mitigazione |
|---------|:-----------:|-------------|
| CV parser non restituisce experiences strutturate | Media | Fallback graceful: se no experiences, lascia years=0.0 |
| Coverage attuale sotto 80% | Alta | Partire con 75% come primo step, poi alzare |
| Enricher impreciso su skill generiche | Bassa | Matching fuzzy con threshold, log per tuning |

---

## Decisioni architetturali

1. **Euristica > LLM per Sprint 10**: L'enricher usa pattern matching e date, non LLM. Motivo: velocità di implementazione, nessuna dipendenza esterna, sufficiente per Phase 1.

2. **Coverage threshold progressivo**: Se 80% è troppo aggressivo post-analisi, partire con 75% e alzare a 80% in Sprint 11.

3. **Enricher disaccoppiato**: `enricher.py` è un modulo standalone che riceve dati già parsati. Non dipende dal parser, non chiama API. Facile da testare e da sostituire con LLM in futuro.
