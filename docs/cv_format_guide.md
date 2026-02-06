# CV Format Guide

Questa guida definisce il formato atteso dei CV per il parser DOCX di ProfileBot.  
L’obiettivo è **massimizzare l’accuratezza del parsing** e ridurre le ambiguità tra sezioni.

---

## ✅ Formato Generale Consigliato

- **File**: `.docx`
- **Lingua**: Italiano (supportato anche Inglese per i titoli sezione)
- **Struttura**: sezioni con titoli chiari e coerenti
- **Encoding**: UTF-8 (gestione caratteri speciali: è, à, ù, ò, ì)

---

## 🧭 Sezioni Attese

Il parser riconosce le sezioni principali tramite titoli (case-insensitive):

### 1. Skills / Competenze
**Titoli riconosciuti:**
- Competenze
- Skills
- Technical Skills
- Tecnologie
- Conoscenze

**Esempio:**
```
Competenze
Python, FastAPI, Docker, PostgreSQL
```

---

### 2. Esperienze / Experience
**Titoli riconosciuti:**
- Esperienza
- Experience
- Work History
- Esperienze Professionali

**Formato consigliato:**
```
Esperienze Professionali
- 2021–2024 | Backend Developer | ACME S.p.A.
  Sviluppo API FastAPI, integrazione Qdrant, CI/CD
```

---

### 3. Formazione / Education
**Titoli riconosciuti:**
- Formazione
- Education
- Istruzione
- Studi

**Esempio:**
```
Formazione
- Laurea Magistrale in Informatica – Università di Torino (2019)
```

---

### 4. Certificazioni / Certifications
**Titoli riconosciuti:**
- Certificazioni
- Certifications
- Qualifiche

**Esempio:**
```
Certificazioni
- AWS Certified Solutions Architect
- ISTQB Foundation
```

---

## ⚠️ Note Importanti

- Se una sezione non è chiaramente identificabile, il testo sarà salvato in `raw_text`.
- Tabelle con skill o esperienze sono supportate, ma il testo deve essere leggibile nelle celle.
- CV senza sezioni esplicite verranno processati con euristiche, ma con accuratezza ridotta.

---

## ✅ Esempio Completo Minimo

```
Mario Rossi
Backend Developer

Competenze
Python, FastAPI, PostgreSQL, Docker

Esperienze
2020–2024 | Backend Developer | ACME
- API REST e integrazione database

Formazione
Laurea in Informatica – Univ. Milano (2019)

Certificazioni
AWS Certified Developer
```

---

## 🔍 Suggerimenti per Massimizzare l’Accuratezza

✅ Usa titoli di sezione chiari  
✅ Inserisci punti elenco per esperienze  
✅ Mantieni un ordine logico: Skills → Esperienze → Formazione → Certificazioni  
✅ Evita sezioni miste o troppo generiche

---

Per dubbi o casi particolari, aggiorna questa guida e informa il team.