# Team Agile - ProfileBot

## Composizione del Team

### Product Owner
**Responsabilità:**
- Definizione e prioritizzazione del Product Backlog
- Interfaccia con stakeholder business (HR, Sales, Management)
- Validazione dei requisiti funzionali
- Accettazione delle user story completate
- Definizione dei criteri di successo MVP

**Focus MVP:**
- Requisiti di ricerca profili
- Criteri di match con job description
- Metriche di disponibilità

---

### Solution Architect
**Responsabilità:**
- Design architetturale del sistema RAG
- Scelte tecnologiche (LlamaIndex, Qdrant, etc.)
- Definizione delle interfacce tra componenti
- Performance e scalabilità
- Code review architetturali

**Focus MVP:**
- Architettura skill-first
- Separazione knowledge store / state store
- Pipeline di indexing

---

### Data Science Specialist
**Responsabilità:**
- Design della pipeline di embedding
- Ottimizzazione dei parametri di retrieval
- Normalizzazione delle skill (dizionario)
- Tuning dei parametri LLM
- Metriche di qualità del matching

**Focus MVP:**
- Modello di embedding per skill
- Algoritmo di ranking
- Valutazione qualitativa dei risultati

---

### Backend Developer(s)
**Responsabilità:**
- Implementazione API FastAPI
- Integrazione con Qdrant
- Pipeline di ingestion CV
- Gestione stato operativo
- Testing e CI/CD

**Focus MVP:**
- Endpoint di ricerca
- Parser documenti CV
- Integrazione LLM

---

### Frontend Developer
**Responsabilità:**
- Interfaccia chatbot
- Dashboard di visualizzazione risultati
- UX/UI del sistema di ricerca
- Responsive design

**Focus MVP:**
- Chat interface minimale
- Visualizzazione risultati di ricerca
- Filtri di disponibilità

---

## Cerimonie Agile

| Cerimonia | Frequenza | Durata | Partecipanti |
|-----------|-----------|--------|--------------|
| Daily Standup | Giornaliera | 15 min | Tutto il team |
| Sprint Planning | Ogni 2 settimane | 2 ore | Tutto il team |
| Sprint Review | Fine sprint | 1 ora | Team + Stakeholder |
| Sprint Retrospective | Fine sprint | 1 ora | Tutto il team |
| Backlog Refinement | Settimanale | 1 ora | PO + Tech Lead |

---

## Definition of Done

Una user story è considerata "Done" quando:

1. ✅ Codice implementato e testato
2. ✅ Code review completata
3. ✅ Test unitari passati (coverage > 80%)
4. ✅ Documentazione aggiornata
5. ✅ Demo al PO completata
6. ✅ Merge in branch develop

---

## Sprint 0 - Setup (1 settimana)

**Obiettivi:**
- [ ] Repository GitHub configurato
- [ ] Ambiente di sviluppo standardizzato
- [ ] CI/CD pipeline base
- [ ] Qdrant locale funzionante
- [ ] Primo CV indicizzato (proof of concept)

---

## Comunicazione

| Canale | Uso |
|--------|-----|
| Slack #profilebot | Comunicazione quotidiana |
| GitHub Issues | Tracking task e bug |
| GitHub Projects | Board Kanban sprint |
| Confluence/Notion | Documentazione estesa |
