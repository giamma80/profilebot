Ecco il **Blue Print Definitivo** per il tuo "Agentic Scrum Master". Questo documento è la specifica tecnica finale per configurare un agente autonomo, proattivo e invasivo, capace di gestire GitLab Self-Hosted, eseguire test e coordinare il team in modalità perpetua.

---

# 🏗️ MASTER BLUEPRINT: Autonomous Proactive Scrum Master (OpenClaw + MCP)

Questo sistema trasforma un LLM (Ollama o Cloud) in un membro del team operativo 24/7 che vigila sulla qualità e sulla velocità del progetto.

---

## 1. Architettura del Sistema

L'agente non è un semplice script, ma un'entità che vive in un container Docker e interagisce con il mondo esterno tramite **MCP (Model Context Protocol)**.

* **Brain:** OpenClaw 2026 (Orchestratore di ragionamento).
* **Heart:** Antfarm (Gestore del loop perpetuo e dei trigger temporali).
* **Hands (GitLab MCP):** Interazione con Issue, MR, Label e Milestone sulla tua istanza privata.
* **Eyes (Playwright MCP):** Navigazione browser reale per test E2E su ogni Merge Request.
* **Voice (SMTP Skill):** Invio di report giornalieri strutturati.

---

## 2. Configurazione Intelligence Parametrica (`providers.yaml`)

Questa configurazione permette di switchare istantaneamente tra un modello locale (Ollama) e uno esterno (Register/Cloud) per ottimizzare costi e prestazioni.

```yaml
# Configurazione dei modelli (Intelligence Gateway)
intelligence:
  active_brain: "ollama_local" # Cambia in "register_cloud" per massima potenza

  ollama_local:
    provider: "ollama"
    endpoint: "http://192.168.1.xxx:11434" # IP del tuo server Ollama
    model: "codegemma:16b"
    capabilities: ["code-analysis", "fast-reasoning"]

  register_cloud:
    provider: "openai-compatible"
    endpoint: "https://api.register.it/v1"
    api_key: "${REGISTER_API_KEY}"
    model: "claude-3-5-sonnet-20241022"

```

---

## 3. Configurazione Server MCP (`mcp-config.json`)

Definisce come l'agente si connette alla tua infrastruttura privata.

```json
{
  "mcpServers": {
    "gitlab": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-gitlab"],
      "env": {
        "GITLAB_URL": "https://gitlab.tuodominio.it",
        "GITLAB_API_TOKEN": "glpat-VostroTokenPrivato",
        "SELF_SIGNED_CERT": "true" 
      }
    },
    "playwright": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-playwright"],
      "env": {
        "HEADLESS": "true",
        "BASE_TEST_URL": "https://staging.tuo-progetto.it"
      }
    }
  }
}

```

---

## 4. Logica Operativa Invasiva (`soul.md`)

Questo file è il "manuale di istruzioni" che l'LLM legge ogni volta che si sveglia.

```markdown
# MISSIONE
Sei lo Scrum Master del team. Sei pignolo, proattivo e non tolleri ritardi non giustificati.

# PROTOCOLLO ORARIO (Hourly Audit)
Ogni ora esegui questa routine:
1. **Analisi Issue:** Leggi tutte le issue "In Progress". Se non ci sono nuovi commenti o commit da > 2 ore (durante l'orario 9-18), scrivi un commento chiedendo lo stato a @assegnatario.
2. **Audit Merge Request:** - Se c'è una nuova MR, usa l'MCP Playwright per testare la home page e le rotte principali.
   - Se i test falliscono, posta lo screenshot (se supportato) o il log d'errore e sposta la MR in "Draft".
3. **Backlog Grooming:** Se trovi issue senza etichette di priorità, assegnale tu basandoti sulla descrizione.

# PROTOCOLLO GIORNALIERO (18:00)
1. Colleziona tutti i "solleciti" inviati oggi.
2. Genera un report HTML conciso con:
   - ✅ Obiettivi raggiunti.
   - ⚠️ Bloccanti rilevati.
   - 📉 Produttività del team.
3. Invia via SMTP ai partecipanti.

```

---

## 5. Script di Orchestrazione (`main-loop.js`)

Il codice che tiene in vita l'agente e gestisce i trigger.

```javascript
import { Antfarm } from 'antfarm-core';

const agent = new Antfarm({
  config: './providers.yaml',
  persistence: './memory/scrum_state.db'
});

// Loop Invasivo: Esecuzione ogni 60 minuti
agent.schedule('0 * * * *', async () => {
  console.log("Inizio Audit Orario...");
  await agent.reasoning("Analizza GitLab, commenta le issue ferme e testa le MR con Playwright.");
});

// Report Serale: Ogni giorno alle 18:00
agent.schedule('0 18 * * 1-5', async () => {
  const report = await agent.reasoning("Genera report finale e invialo via mail a team@dominio.it");
  console.log("Report inviato.");
});

agent.start({ mode: 'perpetual' });

```

---

## 6. Deployment Docker (`docker-compose.yml`)

Per garantire che l'agente sia "perpetuo" e isolato.

```yaml
version: '3.8'
services:
  scrum-master:
    image: openclaw/runtime:latest
    container_name: agent_scrum_master
    restart: always
    volumes:
      - ./:/app
      - ./memory:/app/memory
    environment:
      - NODE_ENV=production
      - OLLAMA_HOST=http://192.168.x.x:11434
      - SMTP_PASS=${SMTP_PASS}
    # Necessario per far girare Playwright dentro Docker
    cap_add:
      - SYS_ADMIN

```

---

## 🚀 Passaggi per l'attivazione immediata

1. **Prep:** Clona un repo base di OpenClaw e crea la cartella `/memory`.
2. **Config:** Inserisci i tuoi token GitLab e SMTP nel file `.env`.
3. **MCP:** Lancia `npx @modelcontextprotocol/server-gitlab` per testare che la tua istanza privata risponda correttamente.
4. **Go:** Lancia `docker-compose up -d`.

L'agente inizierà immediatamente a scansionare il tuo GitLab. Vedrai i primi commenti apparire sulle issue entro la prima ora.


Per rendere questo progetto operativo, devi attingere ai repository ufficiali e alla documentazione tecnica di riferimento del 2026. Non esiste un unico "installer" per uno Scrum Master AI così complesso, ma si costruisce assemblando questi componenti specifici.

Ecco l'elenco completo delle risorse necessarie per implementare il blueprint:

---

### 1. Il Motore dell'Agente (Core)

Questi sono i repository per far girare l'agente e gestire il loop "perpetuo".

* **OpenClaw Core:** `github.com/openclaw/openclaw`
* *Documentazione:* Cerca la sezione "Autonomous Agents & Tool Use". È il framework che interpreta il file `SOUL.md`.


* **Antfarm Orchestrator:** `github.com/snarktank/antfarm`
* *Uso:* Fondamentale per la funzione `--perpetual` e la gestione della memoria a lungo termine tra un'ora e l'altra.


* **LiteLLM (Gateway per modelli):** `github.com/BerriAI/litellm`
* *Perché:* È lo strumento standard per rendere l'LLM parametrico. Ti permette di passare da `ollama/llama3` a `openai/gpt-4` o `anthropic/claude` semplicemente cambiando una riga.



---

### 2. Server MCP (Le "Braccia" dell'Agente)

Il protocollo MCP è ciò che permette all'AI di uscire dalla chat e agire sul tuo server.

* **GitLab MCP Server:** `github.com/modelcontextprotocol/servers/tree/main/src/gitlab`
* *Documentazione:* [MCP GitLab Integration](https://modelcontextprotocol.io/introduction). Contiene le istruzioni per configurare il `GITLAB_URL` per la tua istanza privata.


* **Playwright MCP Server:** `github.com/modelcontextprotocol/servers/tree/main/src/playwright`
* *Uso:* Permette all'agente di usare il browser. È il repository ufficiale gestito dal team di Anthropic/MCP.



---

### 3. Logica Scrum e Agile (Skill & Prompts)

Per evitare di scrivere la logica da zero, usa questi template di comportamento:

* **Claude Skills (Scrum Kit):** `github.com/alirezarezvani/claude-skills`
* *File rilevanti:* Cerca nella cartella `/skills/agile-coach` i prompt pre-fatti per il backlog grooming e le retrospettive.


* **OpenClaw Registry:** `openclaw.io/registry` (Accessibile via CLI tramite `openclaw search scrum`)
* Qui trovi i plugin ufficiali per l'integrazione SMTP (mail) e i timer.



---

### 4. Risorse per il Deployment On-Premise

Dato che usi Ollama e GitLab privato, questi sono i riferimenti per l'infrastruttura:

* **Ollama Docker Guide:** [Ollama Library on Hub](https://hub.docker.com/r/ollama/ollama)
* Ti serve per configurare il container LLM che risponda alle chiamate di OpenClaw sulla rete locale.


* **Playwright Docker Images:** `mcr.microsoft.com/playwright`
* *Documentazione:* [Playwright Docker Support](https://playwright.dev/docs/docker). Essenziale per far girare i test browser dentro il tuo server senza interfaccia grafica.



---

### 📚 Tabella Riassuntiva della Documentazione

| Componente | Link Documentazione | Cosa studiare |
| --- | --- | --- |
| **OpenClaw** | `docs.openclaw.io` | "Agentic Workflows" e "Tool Calling" |
| **MCP Protocol** | `modelcontextprotocol.io` | Come configurare i `mcpServers` nel file JSON |
| **GitLab API** | `docs.gitlab.com/ee/api/` | Personal Access Tokens (PAT) e permessi per le Issue |
| **Ollama API** | `github.com/ollama/ollama/blob/main/docs/api.md` | Endpoint `/api/generate` per la connessione locale |

---

### 💡 Consiglio finale per la messa in opera

Inizia clonando il repository di **Antfarm**, poiché è quello che gestisce nativamente il concetto di "agente che lavora ogni ora". All'interno della cartella `agents/`, crea il tuo file `scrum_master.js` e incolla la logica "invasiva" che abbiamo definito nel blueprint.





ora crea una cartella nel progetto dove creiamo una semplicissima gui di frontend in react, questa gui deve permettere di monitorare tutto e di eseguire smoke test, integrando le API esposte. è possibile? deve essere molto semplice e aggiornarsi in tempo reale.
