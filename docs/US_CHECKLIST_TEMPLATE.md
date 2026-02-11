# User Story Checklist Template

> **Scopo:** checklist uniforme per tutte le User Stories (US), allineata al livello di dettaglio di US‑007.

---

## 📌 Story Info
- **ID:** US-XXX
- **Titolo:** …
- **Sprint:** …
- **Priority:** …
- **Feature Branch:** `feature/US-XXX-descrizione-breve`
- **Dipendenze:** …

---

## ✅ Acceptance Criteria (AC)
- [ ] AC-1: …
- [ ] AC-2: …
- [ ] AC-3: …
- [ ] AC-4: …
- [ ] AC-5: …

---

## 🧱 Scope / Non-Scope
**Scope**
- [ ] …
- [ ] …

**Non-Scope**
- [ ] …

---

## 🧾 Data Contract (Schema)
- [ ] Definizione campi (nome, tipo, obbligatorietà)
- [ ] Validazioni (range, enum, formato)
- [ ] Esempio payload / CSV / JSON
- [ ] Compatibilità backward (se necessaria)

---

## 🧠 Core Logic
- [ ] Funzioni pubbliche con type hints
- [ ] Docstring Google style (solo funzioni pubbliche)
- [ ] Error handling con eccezioni specifiche
- [ ] Logging con lazy formatting (`%s`)
- [ ] No magic numbers

---

## 🌐 API Layer (se applicabile)
- [ ] Endpoint definiti (path, method, status code)
- [ ] Request/Response models (Pydantic v2)
- [ ] Validazioni input (errori 4xx coerenti)
- [ ] OpenAPI aggiornata

---

## 🗄️ Storage / Cache (se applicabile)
- [ ] Namespace/keyspace definito
- [ ] TTL configurabile (se cache)
- [ ] Strategie di miss/fallback
- [ ] Migrazioni o seed (se necessario)

---

## ⏱️ Scheduling & Jobs (se applicabile)
- [ ] Task Celery definita
- [ ] Scheduling via Celery Beat
- [ ] Variabili `.env` documentate
- [ ] Monitoring (Flower)

---

## 🧪 Testing
- [ ] Unit test per core logic
- [ ] Test per edge cases principali
- [ ] Test per error handling
- [ ] Test per integrazione (se necessario)
- [ ] Coverage ≥ 80% sui moduli coinvolti

---

## 📚 Documentation
- [ ] README/Docs aggiornate
- [ ] Guide / format spec aggiornate
- [ ] Examples (payload / file)

---

## ✅ Definition of Done (DoD)
- [ ] AC soddisfatti
- [ ] Test passano
- [ ] Lint + format OK
- [ ] OpenAPI valida
- [ ] PR pronta con checklist compilata