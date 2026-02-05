#!/bin/bash
# Script per creare le issue GitHub iniziali
# Esegui con: ./scripts/create_github_issues.sh

# Assicurati di essere autenticato con: gh auth login

# Labels
gh label create "user-story" --color "0E8A16" --description "User Story" 2>/dev/null
gh label create "epic" --color "7057FF" --description "Epic" 2>/dev/null
gh label create "P0-critical" --color "D93F0B" --description "Priority: Critical" 2>/dev/null
gh label create "P1-high" --color "FF9F1C" --description "Priority: High" 2>/dev/null
gh label create "P2-medium" --color "FBCA04" --description "Priority: Medium" 2>/dev/null
gh label create "P3-low" --color "C5DEF5" --description "Priority: Low" 2>/dev/null
gh label create "sprint-1" --color "1D76DB" --description "Sprint 1" 2>/dev/null
gh label create "sprint-2" --color "1D76DB" --description "Sprint 2" 2>/dev/null
gh label create "sprint-3" --color "1D76DB" --description "Sprint 3" 2>/dev/null
gh label create "sprint-4" --color "1D76DB" --description "Sprint 4" 2>/dev/null
gh label create "sprint-5" --color "1D76DB" --description "Sprint 5" 2>/dev/null

echo "Labels created!"

# Epic Issues
gh issue create --title "[EPIC] Infrastructure Setup" \
  --body "Configurazione ambiente e infrastruttura base per ProfileBot.

## User Stories incluse:
- US-001: Setup Repository e CI/CD
- US-002: Setup Qdrant Vector Store" \
  --label "epic"

gh issue create --title "[EPIC] Document Ingestion" \
  --body "Pipeline per processare e indicizzare i CV.

## User Stories incluse:
- US-003: Parser CV DOCX
- US-004: Skill Extraction e Normalizzazione
- US-005: Embedding e Indexing Pipeline" \
  --label "epic"

gh issue create --title "[EPIC] Search & Matching" \
  --body "Funzionalità di ricerca e matching profili.

## User Stories incluse:
- US-006: API Ricerca Profili per Skill
- US-007: Filtro Disponibilità
- US-008: Match con Job Description" \
  --label "epic"

gh issue create --title "[EPIC] LLM Integration" \
  --body "Integrazione con modelli linguistici per decisioni spiegate.

## User Stories incluse:
- US-009: LLM Decision Engine
- US-010: Source Attribution" \
  --label "epic"

gh issue create --title "[EPIC] User Interface" \
  --body "Interfaccia utente per interazione con il sistema.

## User Stories incluse:
- US-011: Chat Interface Base
- US-012: Visualizzazione Profili" \
  --label "epic"

echo "Epics created!"

# Sprint 1 - User Stories
gh issue create --title "[US-001] Setup Repository e CI/CD" \
  --body "**Come** sviluppatore
**Voglio** un repository Git configurato con CI/CD
**Per** poter collaborare e deployare in modo automatizzato

## Acceptance Criteria
- [ ] Repository GitHub creato
- [ ] Branch protection su main
- [ ] GitHub Actions per test e lint
- [ ] Pre-commit hooks configurati

**Story Points:** 3" \
  --label "user-story,P0-critical,sprint-1"

gh issue create --title "[US-002] Setup Qdrant Vector Store" \
  --body "**Come** data scientist
**Voglio** un'istanza Qdrant configurata
**Per** poter indicizzare e cercare i CV

## Acceptance Criteria
- [ ] Qdrant running (docker-compose)
- [ ] Collection cv_skills creata
- [ ] Collection cv_experiences creata
- [ ] Script di test connessione

**Story Points:** 5" \
  --label "user-story,P0-critical,sprint-1"

gh issue create --title "[US-003] Parser CV DOCX" \
  --body "**Come** sistema
**Voglio** estrarre testo strutturato dai CV in formato DOCX
**Per** poter processare i curriculum aziendali

## Acceptance Criteria
- [ ] Parsing sezioni (skill, esperienze, formazione)
- [ ] Estrazione metadata (nome, ruolo)
- [ ] Gestione errori per file malformati
- [ ] Unit test con CV di esempio

**Story Points:** 8" \
  --label "user-story,P0-critical,sprint-1"

# Sprint 2 - User Stories
gh issue create --title "[US-004] Skill Extraction e Normalizzazione" \
  --body "**Come** data scientist
**Voglio** estrarre e normalizzare le skill dai CV
**Per** avere un vocabolario controllato di competenze

## Acceptance Criteria
- [ ] Dizionario skill base (100+ entry)
- [ ] Mapping sinonimi → skill normalizzate
- [ ] Confidence score per ogni mapping
- [ ] Log skill non riconosciute

**Story Points:** 13" \
  --label "user-story,P0-critical,sprint-2"

gh issue create --title "[US-005] Embedding e Indexing Pipeline" \
  --body "**Come** sistema
**Voglio** generare embedding e indicizzare in Qdrant
**Per** abilitare la ricerca semantica

## Acceptance Criteria
- [ ] Embedding con OpenAI/sentence-transformers
- [ ] Upsert in cv_skills collection
- [ ] Upsert in cv_experiences collection
- [ ] Metadata completi (cv_id, section_type, etc.)
- [ ] Pipeline idempotente

**Story Points:** 13" \
  --label "user-story,P0-critical,sprint-2"

# Sprint 3 - User Stories
gh issue create --title "[US-006] API Ricerca Profili per Skill" \
  --body "**Come** utente
**Voglio** cercare profili in base a skill richieste
**Per** trovare candidati con competenze specifiche

## Acceptance Criteria
- [ ] Endpoint POST /api/search/skills
- [ ] Input: lista skill, filtri (seniority, domain)
- [ ] Output: lista profili ranked con score
- [ ] Paginazione risultati

**Story Points:** 8" \
  --label "user-story,P1-high,sprint-3"

gh issue create --title "[US-007] Filtro Disponibilità" \
  --body "**Come** utente
**Voglio** filtrare i profili per stato di disponibilità
**Per** vedere solo candidati effettivamente assegnabili

## Acceptance Criteria
- [ ] Filtri: only_free, free_or_partial, any
- [ ] Integrazione con source stato operativo
- [ ] Cache stato con TTL
- [ ] Risposta esplicita se nessuno disponibile

**Story Points:** 5" \
  --label "user-story,P1-high,sprint-3"

# Sprint 4 - User Stories
gh issue create --title "[US-008] Match con Job Description" \
  --body "**Come** utente
**Voglio** trovare il miglior profilo per una job description
**Per** proporre candidati ad opportunità specifiche

## Acceptance Criteria
- [ ] Endpoint POST /api/match/job
- [ ] Input: testo job description
- [ ] Estrazione automatica skill richieste
- [ ] Ranking profili con spiegazione LLM
- [ ] Output strutturato con motivazione

**Story Points:** 13" \
  --label "user-story,P1-high,sprint-4"

gh issue create --title "[US-009] LLM Decision Engine" \
  --body "**Come** sistema
**Voglio** usare un LLM per decisioni di matching spiegate
**Per** fornire risposte comprensibili e motivate

## Acceptance Criteria
- [ ] Integrazione OpenAI/Azure OpenAI
- [ ] System prompt ottimizzato skill-first
- [ ] Context normalization per CV
- [ ] Output con cv_id + decision_reason
- [ ] Temperature bassa (0.0-0.3)

**Story Points:** 8" \
  --label "user-story,P1-high,sprint-4"

# Sprint 5 - User Stories
gh issue create --title "[US-010] Source Attribution" \
  --body "**Come** utente
**Voglio** sapere da dove viene ogni affermazione del sistema
**Per** verificare e fidarmi delle raccomandazioni

## Acceptance Criteria
- [ ] Riferimento a CV_ID per ogni claim
- [ ] Sezione (skill/experience) citata
- [ ] Log tracciabile per audit

**Story Points:** 5" \
  --label "user-story,P2-medium,sprint-5"

gh issue create --title "[US-011] Chat Interface Base" \
  --body "**Come** utente
**Voglio** un'interfaccia chat semplice
**Per** interagire con il sistema in linguaggio naturale

## Acceptance Criteria
- [ ] Input testuale
- [ ] Visualizzazione risposta formattata
- [ ] Storico conversazione
- [ ] Responsive design

**Story Points:** 8" \
  --label "user-story,P2-medium,sprint-5"

gh issue create --title "[US-012] Visualizzazione Profili" \
  --body "**Come** utente
**Voglio** vedere i dettagli dei profili suggeriti
**Per** valutare i candidati proposti

## Acceptance Criteria
- [ ] Card profilo con skill
- [ ] Badge disponibilità
- [ ] Esperienze rilevanti
- [ ] Link a CV completo

**Story Points:** 5" \
  --label "user-story,P2-medium,sprint-5"

echo "All issues created successfully!"
echo ""
echo "Next steps:"
echo "1. Create a GitHub Project board"
echo "2. Link issues to the project"
echo "3. Assign team members"
