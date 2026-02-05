# ProfileBot

Sistema AI per il matching di profili professionali basato su competenze (skill-first approach).

## Descrizione

ProfileBot è un'applicazione aziendale che permette la ricerca e analisi dei profili interni, combinando:
- **Curriculum** (docx) con esperienze e skill in formato keyword
- **Stato operativo** (disponibilità/allocazione) da fonti esterne

### Funzionalità MVP

1. **Ricerca profili per skill** - Trovare profili in base a competenze specifiche
2. **Analisi disponibilità** - Identificare profili disponibili, parzialmente allocati o liberi
3. **Match con job description** - Trovare il miglior profilo per una posizione specifica

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python 3.11+ |
| RAG Framework | LlamaIndex |
| Vector Store | Qdrant |
| LLM | OpenAI / Azure OpenAI |
| Queue | Redis |
| API | FastAPI |

## Architettura

```
Client (Chatbot)
       │
       ▼
Backend RAG API ──► Filtro Disponibilità
       │                    │
       ▼                    ▼
Filtro Metadata (skill_domain, seniority)
       │
       ▼
Qdrant – cv_skills (vector search)
       │
       ▼
Shortlist cv_id
       │
       ▼
Qdrant – cv_experiences (supporto)
       │
       ▼
LLM ──► Decisione spiegata
```

## Quick Start

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/profilebot.git
cd profilebot

# Setup environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Run
python -m src.api.main
```

## Project Structure

```
profilebot/
├── src/
│   ├── api/          # FastAPI endpoints
│   ├── core/         # Core business logic
│   ├── services/     # External services (Qdrant, LLM)
│   └── utils/        # Utilities
├── docs/             # Documentation
├── tests/            # Test suite
├── scripts/          # Utility scripts
└── .github/          # GitHub templates
```

## Team

| Ruolo | Responsabilità |
|-------|----------------|
| Product Owner | Priorità backlog, requisiti business |
| Solution Architect | Architettura, decisioni tecniche |
| Data Scientist | Pipeline ML, embedding, ottimizzazione |
| Backend Developer | API, integrations, core logic |
| Frontend Developer | UI/UX chatbot interface |

## Contributing

Vedi [CONTRIBUTING.md](docs/CONTRIBUTING.md)

## License

Proprietario - Uso interno aziendale
