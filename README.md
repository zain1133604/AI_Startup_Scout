# 🛡️ The Startup Scout
### Autonomous Multi-Agent VC Due Diligence Platform

> Upload a pitch deck. Get a full investment dossier in minutes — founder profiles, funding history, competitor analysis, community sentiment, burn rate, and a scored verdict. No analysts required.

---

## What It Does

The Startup Scout is a multi-agent AI system that automates the first stage of venture capital due diligence. You upload a PDF pitch deck, and four specialized AI agents collaborate in a pipeline to produce a structured, sourced investment report — complete with a scored verdict and downloadable PDF dossier.

It doesn't summarize the deck. It goes beyond it — hitting live web sources, job boards, Reddit, and funding databases to build a picture of the company as it exists today, not just as it presents itself.

---

## Agent Pipeline

```
📄 Pitch Deck (PDF)
        │
        ▼
┌─────────────────┐
│   SUMMARIZER    │  Extracts company name, founders, ask, burn rate,
│   Gemini Flash  │  moat, and missing data gaps from the deck
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   RESEARCHER    │  Live web research via Tavily — funding rounds,
│   Gemini Flash  │  ARR, headcount, investors, Reddit sentiment,
│   + Tavily      │  hiring pulse, competitor matrix
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    ANALYST      │  Calculates burn rate, runway, valuation multiples,
│   Llama 3.3 70B │  investment score across 5 scoring pillars
│   (Groq)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     CRITIC      │  Devil's advocate audit — red flags, platform risk,
│   Llama 3.3 70B │  churn signals, moat reality check, final verdict
│   (Groq)        │
└────────┬────────┘
         │
         ▼
📊 Investment Dossier + PDF Report
```

---

## Output

Every analysis produces a structured dossier covering:

| Field | Description |
|-------|-------------|
| `investment_score` | 0–100 composite score across 5 pillars |
| `verdict` | Should Buy / Watchlist / Don't Buy |
| `total_funding` | Sourced from live web with citation URLs |
| `latest_valuation` | Reported or benchmark-estimated |
| `annual_revenue` | ARR with source links |
| `headcount` | Current employee count |
| `runway_months` | Calculated from burn rate and funding |
| `founders` | Names, roles, bios, LinkedIn |
| `funding_history` | All rounds with amounts, dates, investors |
| `competitors` | 3–7 competitors with threat levels |
| `moat_description` | Competitive advantage assessment |
| `hiring_status` | Aggressive / Maintain / Freeze |
| `vibe_score` | Community sentiment score (1–10) |
| `community_sentiment` | Reddit and web sentiment summary |
| `sources` | Citation URLs for every key metric |
| `critic_verdict` | Full narrative audit with red flags |

---

## Scoring Model

The investment score (0–100) is calculated deterministically across five pillars:

```
Pillar A — Financial Health     (max 30 pts)   Runway ≥ 24mo: +30, ≥ 12mo: +15
Pillar B — Traction & Scale     (max 30 pts)   Revenue presence + hiring signal
Pillar C — Team & Pedigree      (max 20 pts)   YC, FAANG, Ivy, serial founder signals
Pillar D — Moat & Vibe          (max 20 pts)   Sentiment score + patent/first-mover
Pillar E — Revenue Gate         (hard cap)     Pre-revenue companies capped at 80
```

The Critic agent then applies final adjustments:
- Platform ban risk: −15 pts
- High churn signal: −10 pts  
- Proprietary moat confirmed: +5 pts
- Vibe score < 3.0: ×0.8 multiplier
- Vibe score > 8.0: ×1.1 multiplier

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LangGraph (StateGraph) |
| Summarizer | Google Gemini 2.5 Flash Lite |
| Researcher | Google Gemini 2.5 Flash Lite + Tavily Search |
| Analyst & Critic | Llama 3.3 70B via Groq |
| PDF Extraction | LlamaParse |
| State Management | Pydantic v2 |
| API | FastAPI + Uvicorn |
| UI | Gradio 5 |
| PDF Reports | ReportLab |
| Deployment | Railway |

---

## Project Structure

```
├── main.py               # FastAPI app — mounts Gradio, serves PDF downloads
├── app_gui.py            # Gradio UI and request bridge
├── graph_manager.py      # LangGraph pipeline — node wiring and state flow
├── state.py              # Pydantic StartupState — single source of truth
├── summarizer.py         # Agent 1 — pitch deck extraction
├── searcher.py           # Agent 2 — live web research
├── analyistagent.py      # Agent 3 — financial scoring engine
├── critic.py             # Agent 4 — investment audit and verdict
├── researchertools.py    # Tavily web search and hiring pulse tools
├── textextractor.py      # LlamaParse PDF extraction
├── report_generator.py   # ReportLab PDF dossier generator
└── requirements.txt
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/your-username/startup-scout
cd startup-scout
pip install -r requirements.txt
```

### 2. Environment variables

Create a `.env` file:

```env
GEMINI_KEY=your_google_gemini_api_key
GROK_KEY=your_groq_api_key
TAVILY_KEY=your_tavily_api_key
LLAMA_PARSE_KEY=your_llamaparse_api_key
```

### 3. Run locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

Visit `http://localhost:8080/gui` for the dashboard.

---

## API

The REST API accepts pitch deck uploads directly:

```bash
curl -X POST https://your-domain.railway.app/analyze \
  -F "file=@pitch_deck.pdf" \
  -F "mode=normal"
```

**Modes:**
- `normal` — Balanced analysis, looks for growth signals
- `hard` — Devil's advocate mode, prioritizes red flags

**Response:** Full `StartupState` JSON object with all fields populated.

---

## Deployment (Railway)

1. Push your repo to GitHub
2. Connect to Railway and set environment variables
3. Railway auto-detects the `uvicorn` start command
4. Your app runs at `https://your-app.up.railway.app`
   - UI: `/gui`
   - API: `/analyze`
   - PDF Downloads: `/download/{filename}`

---

## Requirements

```
fastapi==0.119.0
uvicorn==0.37.0
python-multipart==0.0.20
python-dotenv==1.1.1
langgraph==1.0.8
google-genai==1.62.0
groq>=0.9.0
tavily-python>=0.7.20
llama-parse==0.6.94
pydantic==2.11.7
nest-asyncio==1.6.0
gradio>=5.0.0
PyPDF2==3.0.1
aiohttp==3.10.11
websockets>=13.0.0
reportlab>=4.0.0
```

---

## Limitations

- **Gemini free tier**: 20 requests/day on `gemini-2.5-flash-lite`. Upgrade to a paid plan for production usage.
- **Subsidiary companies**: May require manual verification — the researcher is instructed to research subsidiaries directly but parent company data can bleed through.
- **Reddit sentiment**: Companies with generic names (e.g. "Artisan") may pull unrelated product reviews. The vibe check includes disambiguation logic but isn't perfect.
- **Private companies**: Valuation is estimated using benchmark multiples (15×ARR for SaaS, 20×ARR for AI) when not publicly disclosed.

---

## How It Was Built

This project was built iteratively over a single session — starting from a basic PDF summarizer and evolving into a full multi-agent pipeline. Key architectural decisions:

- **LangGraph** was chosen over a simple sequential chain to enable conditional retry logic (the researcher retries up to 2× if the company name can't be confirmed)
- **Pydantic v2** as the state layer means every agent reads from and writes to the same validated schema — no data loss between hops
- **Separate LLM providers** for different tasks — Gemini for research (better web grounding), Groq/Llama for analysis and critique (faster, deterministic at temperature=0)
- **Safe merge pattern** in the analyst — the LLM only fills fields that are still at default values, preventing re-extraction from overwriting good researcher data

---

## License

MIT License — use freely, attribute if you publish.

---

*Built with LangGraph, Gemini, Groq, Tavily, and too many deploy logs.*
