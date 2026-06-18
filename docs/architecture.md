# AIFORGE Analytics — System Architecture

## Overview

AIFORGE is a 5-tier analytics platform connecting raw AI usage signals to business value metrics.

```
┌──────────────────────────────────────────────────────────────────┐
│  TIER 1 — DATA SOURCES                                           │
│  ┌─────────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ OpenAI/Azure    │  │  GitHub API  │  │   Jira API       │    │
│  │ Usage Export    │  │  REST v3     │  │  (Synthetic)     │    │
│  └────────┬────────┘  └──────┬───────┘  └───────┬──────────┘    │
└───────────┼──────────────────┼──────────────────┼───────────────┘
            │                  │                  │
┌───────────▼──────────────────▼──────────────────▼───────────────┐
│  TIER 2 — INGESTION & GOVERNANCE                                 │
│  src/github/api_client.py  ← PyGithub wrapper                   │
│  src/governance/analyzer.py ← spaCy NER + Regex PII scan        │
│  src/governance/redactor.py ← SHA-256 pseudonymisation           │
│  scripts/run_pipeline.py    ← Orchestrator                       │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│  TIER 3 — STORAGE (SQLite / PostgreSQL)                          │
│  ┌──────────────────┐  ┌──────────────────┐                      │
│  │  users_master    │  │  ai_usage_logs   │                      │
│  │  github_metrics  │  │  jira_tickets    │                      │
│  │  analytics_cache │  │                  │                      │
│  └──────────────────┘  └──────────────────┘                      │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│  TIER 4 — ANALYTICS ENGINE                                       │
│  src/analysis/metrics.py      ← ROI formula engine              │
│  src/analysis/correlation.py  ← Pearson/Spearman/OLS            │
│  src/analysis/optimizer.py    ← Zombie licence detection         │
│  src/jira/ticket_analyzer.py  ← Before/After velocity           │
│  src/github/pr_analyzer.py    ← PR cycle time analysis          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│  TIER 5 — PRESENTATION                                           │
│  app/main.py  →  Streamlit (5 tabs)                             │
│  ├─ Tab 1: Executive Overview (KPIs, trends, benchmarks)        │
│  ├─ Tab 2: Usage Analytics (model mix, heatmap, costs)          │
│  ├─ Tab 3: Productivity Impact (Before/After, regression)       │
│  ├─ Tab 4: Governance & Security (gauge, treemap, incidents)    │
│  └─ Tab 5: Cost Optimisation (zombies, ROI scatter, top users)  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Algorithms

### 1. ROI Formula
```
hours_saved_per_ticket = max(0, avg_cycle_before − avg_cycle_after)
dollar_value_saved     = hours_saved × tickets_closed × hourly_rate
net_roi                = dollar_value_saved − total_ai_cost
pct_improvement        = hours_saved / avg_cycle_before × 100
```

### 2. PII Risk Scoring
```
score = 0
for each NER entity (PERSON/ORG/GPE):    score += weight[entity_type]
for each regex match (email/card/SSN):   score += weight[pattern]
for each sensitive keyword:              score += 20 (capped at 40)
score = min(score, 100)

Risk Level:
  score ≥ 75 → Critical
  score ≥ 50 → High
  score ≥ 25 → Medium
  score <  25 → Low
```

### 3. Zombie Detection
```
median_cost = median(total_ai_cost for all users)
is_zombie = (total_cost > median_cost) AND (tickets_closed == 0) AND (prs_merged == 0)
```

### 4. Correlation (OLS)
```
y = β₀ + β₁·x + ε
Solved via scipy.stats.linregress
R² reported as goodness-of-fit
Pearson r for linear, Spearman ρ for monotonic
```

---

## Data Flow: From Prompt to Dashboard

```
1. Employee types prompt into ChatGPT / Copilot
        ↓
2. Usage log exported (token_count, cost_usd, model_name)
        ↓
3. run_pipeline.py: PII scan via spaCy → risk_score written to DB
        ↓
4. Preprocessor: merge with users_master → enriched DataFrame
        ↓
5. Analytics engine: compute ROI, classify zombies, run correlations
        ↓
6. Streamlit: read from DB → filter → render charts
```

---

## Database Schema (Abbreviated)

| Table | Rows (synthetic) | Key Columns |
|---|---|---|
| `users_master` | 80 | user_id, department, hourly_rate, github_username |
| `ai_usage_logs` | 5,000 | user_id, model_name, token_count, cost_usd, risk_score |
| `jira_tickets_synthetic` | ~1,600 | user_id, cycle_time_hours, period (Before/After) |
| `github_metrics` | Live from API | pr_id, cycle_time_hours, rework_ratio |
| `analytics_cache` | Derived | user_id, month_year, net_roi, hours_saved |

---

## Security Architecture

```
Raw Prompt → [PII Scanner] → [Redactor] → Stored (masked)
                                 ↓
                        risk_score in DB
                        (0–100, 4 levels)
```

The redactor uses **deterministic SHA-256 pseudonymisation** so:
- User identities are masked in exports
- Trend analysis is still possible (same user = same hash)
- Without the salt, identities cannot be recovered

---

## Deployment Options

| Option | Command | Use Case |
|---|---|---|
| Local dev | `streamlit run app/main.py` | Development |
| Docker | `docker-compose up --build` | Staging/demo |
| Cloud | Push image to ECR/GCR + deploy | Production |
