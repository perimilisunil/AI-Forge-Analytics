# 🔷 AIFORGE: Enterprise AI Intelligence & Governance Platform

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white&style=for-the-badge)
![Backend](https://img.shields.io/badge/Backend-Streamlit-red?logo=streamlit&logoColor=white&style=for-the-badge)
![Engine](https://img.shields.io/badge/Engine-SQLite-003B57?logo=sqlite&logoColor=white&style=for-the-badge)
![NLP](https://img.shields.io/badge/NLP-spaCy-09A3D5?logo=spacy&logoColor=white&style=for-the-badge)
![Data](https://img.shields.io/badge/Data-Pandas-150458?logo=pandas&logoColor=white&style=for-the-badge)
![Charts](https://img.shields.io/badge/Charts-Plotly-3F4F75?logo=plotly&logoColor=white&style=for-the-badge)
![API](https://img.shields.io/badge/API-GitHub_REST_v3-181717?logo=github&logoColor=white&style=for-the-badge)

> **A production-grade analytics engine for measuring the real return on enterprise AI investment.**

AIFORGE is an end-to-end data intelligence platform that processes AI usage logs, project management tickets, and live GitHub engineering data to quantify productivity impact, surface security violations, and flag wasted software licences — turning anecdotal "AI is helping us" claims into defensible, board-ready numbers.

---
## 🚀 Live demo

🔗 **Dashboard (Live):** [https://ai-forge-analytics1.streamlit.app](https://aiforgeanalytics.streamlit.app)

> **NOTE:** The dashboard is hosted on Streamlit's free tier and may occasionally crash or run out of memory.
> If the site is down, please email `perimilisunil@gmail.com` and I will restart the app and ensure it runs as expected.
> For better experience switch to **LIGHT MODE** , 
---

## 📖 Project Overview

AIFORGE was built to answer a question almost every engineering leader is being asked right now: *"We pay for Copilot, ChatGPT, and Azure OpenAI — is it actually working?"* Most organizations have no answer beyond a feeling. AIFORGE replaces that feeling with measurement.

The platform ingests three data streams — AI usage telemetry, Jira ticket history, and real GitHub Pull Request data — normalizes them into a relational schema, and runs them through a statistical and NLP analysis pipeline before surfacing everything in a 5-tab interactive dashboard. Its GitHub module deliberately targets **19 real, public, high-traffic repositories** rather than synthetic placeholders, using the public launch of GitHub Copilot (21 June 2022) as a genuine, independently verifiable Before/After boundary.

Key characteristics:

* End-to-end pipeline from raw API ingestion to boardroom-ready ROI figures.
* Multi-layer PII detection combining NLP entity recognition with regex and keyword scanning.
* Real, reproducible GitHub engineering data — not fabricated trend lines.
* Privacy-first design — sensitive prompt text is redacted before any export touches disk.
* Outputs focused on action: ranked licence-waste lists, risk dashboards, and exportable CSVs.

---

## 💻 Technology Stack

| Core Technologies | Component                       | Purpose                                          |
| ------------------ | -------------------------------- | -------------------------------------------------- |
| Runtime             | Python 3.11+                      | Core engine and pipeline orchestration             |
| Data Engineering    | Pandas, NumPy                     | Vectorized transforms, feature engineering         |
| Statistics          | SciPy, scikit-learn               | Pearson/Spearman correlation, OLS regression       |
| NLP / Governance    | spaCy (`en_core_web_sm`)          | Named Entity Recognition for PII detection         |
| Visualization        | Plotly Express & Graph Objects   | Dual-axis, gauge, treemap, diverging-bar charts    |
| Database             | SQLite                            | Relational storage, PostgreSQL-compatible schema   |
| External API          | PyGithub / Requests              | GitHub REST API v3 pagination & rate limiting      |
| Web Framework          | Streamlit                        | Real-time dashboard with `@st.cache_data`          |

---

## 🎯 The Five-Tier Architecture

### Tier 1 — Data Sources
**Logic:** Three independent streams feed the system — live GitHub Pull Request data pulled from 19 real public repositories via REST API v3, AI usage telemetry (OpenAI/Azure export or synthetic), and Jira ticket history.
**Impact:** Every downstream number traces back to a named, inspectable source — nothing is a black box.

### Tier 2 — Ingestion & Governance
**Logic:** Before any row reaches storage, it passes through the Governance Vault — a three-layer PII scanner — and the GitHub client, which labels every PR `Before` or `After` against a fixed, verifiable boundary: the GitHub Copilot public launch (21 June 2022).

- **Layer 1 — spaCy NER:** flags `PERSON`, `ORG`, `GPE`, `MONEY` entities in AI prompts.
- **Layer 2 — Regex:** seven compiled patterns catch emails, card numbers, SSNs, API keys (`sk-`, `ghp-`, `xoxb-`), IPs, and credential URLs.
- **Layer 3 — Keywords:** 25+ terms (`confidential`, `merger`, `nda`) catch domain-specific risk the other two layers miss.

**Impact:** A composite risk score (0–100) is attached to every prompt, and every PR carries a verifiable Before/After label, before either ever touches the database.

### Tier 3 — Storage
**Logic:** A normalized SQLite schema — `users_master`, `ai_usage_logs`, `jira_tickets_synthetic`, `github_metrics`, `analytics_cache` — with 13 indexes and a database-level `CHECK (period IN ('Before','After'))` constraint.
**Impact:** Data integrity is enforced by the engine itself, not just application code — no row can silently corrupt the Before/After analysis.

### Tier 4 — Analytics Engine
**Logic:** Three engines run on top of storage — the **ROI Formula Engine** (converts cycle-time savings into dollar value per user), the **Statistical Engine** (Pearson, Spearman, OLS regression with R²), and the **Licence Classifier** (percentile-based, not fixed thresholds, so it adapts to any spend scale).
**Impact:** Every user lands in one of five categories —   **⭐ Champion · ✅ Healthy · 💤 Underutilized · ⚠️ At-Risk · 🧟 Zombie** — based on measured output,not guesswork.

### Tier 5 — Presentation
**Logic:** A 5-tab Streamlit dashboard renders 40+ Plotly charts on top of a `@st.cache_data` layer, so the entire analytics pipeline runs once and every sidebar interaction reads from memory.
**Impact:** Executives, security teams, and engineering leads each get a dedicated tab — Executive Overview, Usage Analytics, Productivity Impact, Governance & Security, and GitHub Intelligence — without re-running a single query.

---

## 🏗️ System Architecture

```
                        ┌────────────────────────────────────────────────────────────┐
                        │                     Technology Stack                       │
                        │ Runtime · Pandas/NumPy · SciPy · spaCy · Plotly · SQLite   │
                        └────────────────────────────────────────────────────────────┘
                                              ↓
                        ┌────────────────────────────────────────────────────────────┐
                        │ Data Sources                                               │
                        │ ├─ GitHub REST API v3 (19 real public repos)               │
                        │ ├─ AI Usage Logs                                           │
                        │ └─ Jira Ticket History                                     │
                        └────────────────────────────────────────────────────────────┘
                                              ↓
                        ┌────────────────────────────────────────────────────────────┐
                        │ Ingestion & Governance (src/github, src/governance)        │
                        │ ├─ PII Analyzer — spaCy NER + Regex + Keywords             │
                        │ ├─ Redactor — masking + SHA-256 pseudonymisation           │
                        │ └─ run_pipeline.py — Stage 1: PII · Stage 2: GitHub Sync   │
                        └────────────────────────────────────────────────────────────┘
                                              ↓
                        ┌────────────────────────────────────────────────────────────┐
                        │ Storage — SQLite (database/schema.sql)                     │
                        │ users_master · ai_usage_logs · jira_tickets ·github_metrics│
                        └────────────────────────────────────────────────────────────┘
                                              ↓
                        ┌────────────────────────────────────────────────────────────┐
                        │ Analytics Engine (src/analysis, src/github/pr_analyzer)    │
                        │ ├─ ROI Formula Engine                                      │
                        │ ├─ Pearson / Spearman / OLS Regression                     │
                        │ └─ 5-Category Licence Classifier                           │
                        └────────────────────────────────────────────────────────────┘
                                              ↓
                        ┌────────────────────────────────────────────────────────────┐
                        │ Intelligence Layer (app/main.py)                           │
                        │ Streamlit Dashboard —  Tabs ·  Plotly Charts               │
                        └────────────────────────────────────────────────────────────┘
```

---

## 📐 Installation & Setup

**Prerequisites**

* Python 3.11 or higher
* A [GitHub Personal Access Token](https://github.com/settings/tokens) (scope: `public_repo`)
* Git

**Quick Start**

```bash
# Clone the repository
git clone https://github.com/yourusername/AIFORGE_ANALYTICS.git
cd AIFORGE_ANALYTICS

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Add your GitHub token
cp .env.example .env
# edit .env → GITHUB_TOKEN=ghp_your_token_here

# 1. Initialise database + seed synthetic data
python scripts/setup_db.py

# 2. (Optional) Sync real GitHub PR data — 19 repos, ~3 minutes
python scripts/run_pipeline.py --mode live

# 3. Launch the dashboard
streamlit run app/main.py
```

**Dependencies**

```
streamlit>=1.35.0
pandas>=2.2.2
numpy>=1.26.4
plotly>=5.22.0
spacy>=3.7.4
scipy>=1.13.0
scikit-learn>=1.5.0
PyGithub>=2.3.0
python-dotenv>=1.0.1
faker>=25.2.0
loguru>=0.7.2
pytest>=8.2.2
```

---

## ✍️ Usage Guide

**Dashboard Navigation**

1. **Sidebar Controls**

   * Department Filter: `dept` (selects a specific department or "All").
   * Risk Level Filter: `risk_filter` — Low / Medium / High / Critical multi-select.
   * Jira Period Filter: `period_opt` — Before / After / Both.
   * GitHub Contributors Only: `github_only` toggle.

2. **Tab Organization**

   * **Tab 1 — Executive Overview**
     - Daily token & spend trend (dual-axis)
     - Spend and active users by department
     - Department benchmark table
   * **Tab 2 — Usage Analytics**
     - Token distribution histogram
     - Model usage and cost breakdown
     - Day × Hour usage heatmap
   * **Tab 3 — Productivity Impact**
     - Before/After cycle time comparison (Jira)
     - Story points vs cycle time (OLS regression)
     - GitHub PR velocity trend with Copilot launch marker
   * **Tab 4 — Governance & Security**
     - Corporate Risk Index gauge
     - Risk exposure treemap by department
     - Forensic incident log — top 25 flagged prompts
   * **Tab 5 — GitHub Intelligence**
     - Monthly PR cycle time trend (real data, 19 repos)
     - Rework ratio Before/After Copilot
     - Top contributors and repository breakdown tables

3. **Export Options**

   - Processed CSVs: auto-written to `data/processed/` on every pipeline run.
   - Synthetic seed data: exported to `data/synthetic/` by `setup_db.py`.
   - All exports are PII-redacted and user IDs are SHA-256 pseudonymised.

---

---

## 🔏 Privacy & Compliance

**Data Protection Principles**

* PII Redaction: detected emails, card numbers, SSNs, and API keys are masked before any CSV export.
* Pseudonymisation: `user_id` values are replaced with deterministic SHA-256 hashes in exported files.
* No Raw Prompt Exposure: the dashboard's forensic log truncates prompt text to 80 characters.
* Transparency: every detection rule is defined in `src/governance/analyzer.py` and fully auditable.

---

## 📂 Project Structure

```
AIFORGE_ANALYTICS/
├── src/
│   ├── config.py               # Central registry — 19 repos, Copilot date, constants
│   ├── data/
│   │   ├── loader.py            # Unified database access layer
│   │   └── preprocessor.py      # Feature engineering + CSV export
│   ├── governance/
│   │   ├── analyzer.py          # PII detection — NER + regex + keywords
│   │   └── redactor.py          # Masking + pseudonymisation
│   ├── analysis/
│   │   ├── metrics.py           # ROI formula engine
│   │   ├── correlation.py       # Pearson / Spearman / OLS
│   │   └── optimizer.py         # 5-category licence classifier
│   ├── github/
│   │   ├── api_client.py        # GitHub REST API pagination
│   │   └── pr_analyzer.py       # Cycle time, rework ratio, velocity trend
│   └── jira/
│       ├── api_client.py
│       └── ticket_analyzer.py
├── scripts/
│   ├── setup_db.py              # DB init + synthetic data generation
│   └── run_pipeline.py          # Pipeline orchestrator (4 modes)
├── app/
│   ├── main.py                  # Streamlit dashboard — 5 tabs
│   ├── pages/                   # 5 standalone page routes
│   └── components/              # Reusable chart & KPI factories
├── database/
│   ├── schema.sql               # 5 tables, 13 indexes, CHECK constraints
│   └── queries.sql              # Reference analytical SQL
├── tests/
│   ├── test_roi_math.py         # 16 ROI formula tests
│   └── test_pii_detection.py    # 28 PII detection tests
├── data/
│   ├── raw/                     # Raw API responses
│   ├── processed/               # Pipeline output CSVs
│   └── synthetic/                # Auto-generated seed data
├── docs/
│   ├── architecture.md
│   └── api_spec.md
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 🛞 Performance Benchmarks

**System Metrics (Local / Docker deployment)**

| Metric                  |        Value | Notes                                  |
| ------------------------ | ------------: | ---------------------------------------- |
| Dashboard load (cached)   |   < 200ms     | Served from `@st.cache_data`, 10-min TTL |
| Initial data load         |  2–4 seconds  | First load only — all JOINs + transforms |
| GitHub sync (19 repos)    |   ~3 minutes  | ~76 API calls, well within 5,000/hr quota|
| Synthetic data seed        |  < 30 seconds | 100 users, 6,000 logs, 3,500 tickets     |
| Unit test suite            |   < 5 seconds | 44 tests, full coverage of core math     |

**Optimization Strategies**

* `@st.cache_data`: avoids re-querying SQLite on every sidebar interaction.
* Indexed schema: 13 indexes across high-cardinality lookup columns.
* Bounded API pagination: `MAX_PRS_PER_REPO` caps sync time predictably.
* In-memory filtering: sidebar filters operate on cached DataFrames, not SQL.

---

## 🛠️ Development Roadmap

**Phase 1: Foundation**

* [x] Database schema design (`schema.sql`) with Before/After CHECK constraints.
* [x] Synthetic data generator with realistic department/role distributions.
* [x] ROI formula engine (`metrics.py`).

**Phase 2: Intelligence**

* [x] Three-layer PII detection pipeline (`analyzer.py`).
* [x] 19-repository GitHub integration with Copilot-launch boundary.
* [x] 5-category percentile-based licence classifier.
* [x] Pearson / Spearman / OLS statistical analysis.

**Phase 3: Production (Current)**

* [x] Theme-adaptive dashboard CSS (light/dark mode support).
* [x] Docker + Docker Compose deployment.
* [x] 44-test automated suite covering ROI and PII logic.
* [ ] Real-time streaming ingestion (replace batch pipeline).
* [ ] Fine-tuned enterprise PII model (replace generic spaCy model).

---

## 🧳 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add AmazingFeature'`).
4. Run the test suite (`pytest tests/ -v`).
5. Push to the branch and open a Pull Request.

---

## 📃 Acknowledgments

**Built to make AI investment measurable, not anecdotal.**

**Technical Inspiration:**

* GitHub's public REST API and the broader open-source PR history it makes verifiable.
* Streamlit's philosophy of "data apps in pure Python."
* spaCy's industrial-strength NLP pipeline for entity recognition.

---
## 📥 Contact & Support

### Project Maintainer
**Sunil Kumar**  
🔗 [GitHub](https://github.com/perimilisunil)  
🔗 [LinkedIn](https://www.linkedin.com/in/perimili-sunil-kumar-bb22b3300?utm_source=share&utm_campaign=share_via&utm_content=profile&utm_medium=android_app)  
📧 [perimilisunil@gmail.com](mailto:perimilisunil@gmail.com)

