# 🔷 AIFORGE Analytics Platform
### Enterprise AI Intelligence & ROI Measurement System

> **B.Tech Major Project** — End-to-end data platform that bridges the gap between AI spending and measurable business value.

---

## 🎯 The Problem

Organizations are in a **"GenAI Gold Rush"** — spending millions on AI licenses and API tokens while flying completely blind:

- **The ROI Gap**: CFOs cannot verify if AI tools (GitHub Copilot, ChatGPT Enterprise) are increasing productivity or just producing "fast junk"
- **The Security Risk**: Employees accidentally paste PII, API keys, and internal strategy into public LLMs — creating legal liabilities
- **The Zombie Problem**: Up to 40% of AI licenses sit unused, burning budget with zero return

---

## 💡 The Solution

AIFORGE is a **Command Center** that:
1. **Monitors** AI usage across all tools and teams
2. **Calculates** the dollar value of time saved (Before vs After AI adoption)
3. **Flags** security violations and PII leakage in real-time
4. **Optimises** licence costs by identifying unused seats

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DATA SOURCES                          │
│  OpenAI/Azure Usage Logs  ·  Jira API  ·  GitHub API    │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│                  INGESTION LAYER                         │
│  src/jira/api_client.py  ·  src/github/api_client.py    │
│  scripts/run_pipeline.py (orchestrator)                  │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│              PROCESSING & GOVERNANCE LAYER               │
│  src/governance/analyzer.py   (PII Detection — spaCy)   │
│  src/governance/redactor.py   (Anonymisation)            │
│  src/data/preprocessor.py     (Cleaning & Enrichment)   │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│                  ANALYTICS ENGINE                        │
│  src/analysis/metrics.py      (ROI, Risk Scores)        │
│  src/analysis/correlation.py  (Spend vs Productivity)   │
│  src/analysis/optimizer.py    (Zombie Licence Detection) │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│               SQLite DATABASE                            │
│  users_master · ai_usage_logs · jira_tickets_synthetic  │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│                STREAMLIT DASHBOARD                       │
│  app/main.py  →  5 tabs: Executive · Usage · Prod ·     │
│                           Governance · Cost Optimisation │
└─────────────────────────────────────────────────────────┘
```

---

## ⚙️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.11+ | Core engine |
| Data Wrangling | Pandas, NumPy | Cleaning, correlation math |
| NLP / Security | spaCy (en_core_web_sm) | PII detection, NER |
| Database | SQLite (dev) / PostgreSQL (prod) | Usage metadata storage |
| Frontend | Streamlit + Plotly | Professional web dashboard |
| Integrations | GitHub REST API v3 | PR / commit metrics |
| Containerisation | Docker + Docker Compose | Reproducible deployment |

---

## 🚀 Quick Start

### 1. Clone and configure
```bash
git clone https://github.com/yourname/aiforge-analytics.git
cd AIFORGE_ANALYTICS
cp .env.example .env
# Edit .env — add your GITHUB_TOKEN (personal access token, scope: public_repo)
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 3. Initialise database + generate synthetic data
```bash
python scripts/setup_db.py
```
This seeds 100 users, 6,000 usage log entries, 3,500 Jira tickets (Before/After),
and 19 × 120 = 2,280 synthetic GitHub PRs so the dashboard works immediately.

### 4. Launch dashboard (synthetic data)
```bash
streamlit run app/main.py
```

### 5. Sync real GitHub PR data (live mode)
```bash
# Full sync — all 19 repos, ~7,600 real PRs, ~2 minutes
python scripts/run_pipeline.py --mode live

# Or test with a single repo first
python scripts/run_pipeline.py --mode github-only --repo microsoft/vscode --max-prs 200
```

### 6. (Optional) Docker
```bash
docker-compose up --build
# Dashboard at http://localhost:8501
```

---

## 🗂️ GitHub Data Strategy

No private organisation required. The platform fetches from **19 world-class
public repos** mapped to 7 departments:

| Department | Repos |
|---|---|
| Engineering | microsoft/vscode · microsoft/TypeScript · electron/electron |
| Frontend | facebook/react · vuejs/core · angular/angular |
| Backend | django/django · fastapi/fastapi · expressjs/express |
| DevOps | kubernetes/kubernetes · docker/compose · hashicorp/terraform |
| Data Science | scikit-learn/scikit-learn · pandas-dev/pandas · pytorch/pytorch |
| Security | OWASP/CheatSheetSeries · anchore/grype |
| Mobile | flutter/flutter · facebook/react-native |

**Before/After AI boundary:** GitHub Copilot public launch — **21 June 2022**.
PRs merged before this date = "Before AI era". PRs after = "After AI era".
This is real, verifiable, industry-documented — not fabricated.

---

## 📁 Project Structure

```
AIFORGE_ANALYTICS/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .env                         # API keys (never commit)
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── data/
│   ├── raw/                     # Raw API responses
│   ├── processed/               # Cleaned data
│   └── synthetic/               # Generated test data
├── notebooks/                   # EDA and experiments
├── scripts/
│   ├── setup_db.py              # DB initialisation
│   └── run_pipeline.py          # Full pipeline orchestrator
├── database/
│   ├── schema.sql               # Table definitions
│   └── queries.sql              # Analytics JOINs
├── src/
│   ├── config.py                # Environment & constants
│   ├── data/loader.py           # DB/CSV reader
│   ├── data/preprocessor.py     # Cleaning logic
│   ├── jira/api_client.py       # Jira integration
│   ├── jira/ticket_analyzer.py  # Cycle time calculation
│   ├── github/api_client.py     # GitHub integration
│   ├── github/pr_analyzer.py    # PR metrics
│   ├── governance/analyzer.py   # PII detection (spaCy)
│   ├── governance/redactor.py   # Data masking
│   └── analysis/
│       ├── metrics.py           # ROI + Risk Score engine
│       ├── correlation.py       # Spend vs productivity math
│       └── optimizer.py         # Zombie licence detection
└── app/
    ├── main.py                  # Streamlit entry point
    └── pages/                   # Tab-based pages
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | GitHub Personal Access Token |
| `GITHUB_ORG` | Yes | Your GitHub organisation name |
| `OPENAI_API_KEY` | Optional | For live token cost sync |
| `DB_PATH` | Optional | SQLite path (default: database/aiforge.db) |

---

## 📊 Key Metrics Calculated

- **Net ROI** = (Hours Saved × Hourly Rate) − AI Licence Cost
- **Efficiency Delta** = (Before Avg Cycle Time − After Avg Cycle Time) / Before × 100
- **Risk Score** = Weighted sum of PII density, high-risk flag frequency, and prompt sensitivity
- **Zombie Score** = High AI cost + zero productivity contribution (tickets/PRs)

---

## 🎓 Academic Context

This project was built as a B.Tech Major Project demonstrating:
- Full-stack data engineering (ingestion → storage → analytics → visualisation)
- Applied NLP for enterprise security (PII detection with Named Entity Recognition)
- Causal analysis methodology (Before/After experimental design)
- Software engineering best practices (modular architecture, unit tests, Docker)

---

## 📄 Licence
MIT — for academic use.
