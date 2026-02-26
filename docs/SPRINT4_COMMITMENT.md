# Sprint 4 — Commitment del Team

> **Sprint Goal:** Implementare il layer LLM Decision Engine e il matching con Job Description
> **Periodo:** Sprint 4 (2 settimane)
> **Data documento:** 26 febbraio 2026

---

## Stato del progetto

ProfileBot ha completato il **65% dello scope MVP** (74/113 Story Points). Gli Sprint 1-3 hanno consolidato l'intera pipeline di ingestion, dalla parsificazione dei CV all'indicizzazione in Qdrant, fino alla ricerca semantica per skill e al filtro di disponibilità. Lo Sprint 4 è già a metà: la US-016 (orchestrazione DAG) e la US-017 (monitoring API) sono completate.

Restano **due user story chiave** per chiudere lo Sprint 4 e sbloccare il cuore funzionale del sistema.

---

## Obiettivi Sprint 4 (rimanenti)

### US-009: LLM Decision Engine (8 SP) — Layer Fondativo

Questa storia introduce il modulo `src/core/llm/` che sarà il cervello decisionale di ProfileBot. Si tratta di un layer provider-agnostic che supporta OpenAI, Azure OpenAI e Ollama tramite un'unica configurazione.

**Cosa consegniamo:**

- Client LLM con factory pattern e retry (tenacity), provider switch via `.env`
- System prompt skill-first ottimizzato (derivato dall'analisi preliminare §10)
- Context builder per normalizzare shortlist CV (max 5-7 profili)
- Output strutturato JSON con `DecisionOutput` (Pydantic v2)
- Config centralizzata: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`
- Test unitari con mock client (coverage >= 80%)

**Decisione architetturale — Approccio Leggero:**
Utilizziamo un singolo client OpenAI con `base_url` configurabile. La libreria `openai` supporta nativamente endpoint OpenAI-compatible (Ollama, vLLM, LM Studio). Nessun overhead di Protocol/ABC aggiuntivi. Il provider si cambia via `.env` senza modifiche al codice.

**Stima:** 3-4 giorni di sviluppo

---

### US-008: Match con Job Description (13 SP) — Dipende da US-009

Questa storia orchestra il matching end-to-end: dall'analisi di una job description all'estrazione delle skill richieste, fino al ranking dei candidati con spiegazione LLM.

**Cosa consegniamo:**

- Endpoint `POST /api/v1/match/job`
- Estrazione automatica skill (must-have / nice-to-have) dalla JD via LLM
- Pipeline: LLM extraction → vector search → availability filter → LLM ranking
- Output con score, skill matchate, skill mancanti, spiegazione per candidato
- Response time target < 10 secondi

**Stima:** 5-6 giorni di sviluppo (inizio dopo completamento US-009)

---

## Piano di esecuzione

```
Settimana 1                          Settimana 2
────────────────────────────────     ────────────────────────────────
US-009: LLM Client + Config          US-008: Endpoint + JD Extraction
US-009: Prompts + Schemas            US-008: Ranking Pipeline
US-009: Test + Code Review           US-008: LLM Explanations
US-009: Merge ✓                      US-008: Integration Test + Merge ✓
```

---

## Rischi e mitigazioni

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Rate limiting OpenAI durante sviluppo | Medio | Utilizzare Ollama locale per sviluppo/test, OpenAI per staging |
| Qualità output LLM non sufficiente | Alto | Iterare su system prompt con dataset di 5 JD reali, temperature bassa (0.1) |
| Response time > 10s per matching | Medio | Limitare shortlist a 5-7 profili, streaming se necessario |
| US-009 in ritardo blocca US-008 | Alto | US-009 è priorità assoluta della prima settimana |

---

## Dipendenze esterne

- **OpenAI API key** configurata (o Ollama locale per sviluppo)
- **Dataset di test:** almeno 5 job description reali per validazione prompt
- **CV indicizzati in Qdrant:** già disponibili dalla pipeline esistente

---

## Definition of Done — Sprint 4

Al termine dello sprint, il team consegna:

1. `src/core/llm/` funzionante con test (US-009)
2. `POST /api/v1/match/job` operativo end-to-end (US-008)
3. OpenAPI aggiornata con nuovo endpoint
4. Test passano, lint pulito, coverage >= 80% sui nuovi moduli
5. PR merged con checklist compilata
6. Demo al PO con job description reale

---

## Story Points Summary — Sprint 4

| User Story | SP | Status |
|---|---|---|
| US-016: Orchestrazione DAG | 5 | ✅ Completata |
| US-017: Availability Monitoring | 3 | ✅ Completata |
| US-009: LLM Decision Engine | 8 | ⬅️ Prossimo step |
| US-008: Match Job Description | 13 | ⏳ Dipende da US-009 |
| **Totale Sprint 4** | **29** | **8/29 completati** |

**Velocity media team:** ~22 SP/sprint (Sprint 1-3)
**Capacity rimanente:** 21 SP → allineato con la velocity storica

---

## Impegno del team

Ci impegniamo a consegnare US-009 e US-008 entro la fine dello Sprint 4, con qualità produzione (test, lint, documentazione). La priorità assoluta è US-009 come layer fondativo: senza di esso, US-008 non può iniziare.

Il team si impegna inoltre a:
- Daily standup per visibilità sullo stato
- Code review entro 24h dalla PR
- Segnalare impediment al primo standup utile
- Usare Ollama in locale per iterare velocemente sui prompt senza vincoli di rate-limit

---

*Documento generato il 26/02/2026 — ProfileBot Sprint 4*
