"""
src/config.py
─────────────
Central configuration loader.
Reads .env file, sets DB path, and exposes all runtime constants.

GitHub strategy: Public repo mode (no org required).
15 world-class public repos are mapped to 7 departments.
Before/After AI split: GitHub Copilot public launch — 21 June 2022.
"""

import os
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
from loguru import logger

# ─── Resolve project root ────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent.resolve()
ENV_FILE = ROOT_DIR / ".env"

load_dotenv(ENV_FILE)

# ─── Database ────────────────────────────────────────────
_db_env = os.getenv("DB_PATH", "").strip()
DB_PATH = Path(_db_env) if _db_env else ROOT_DIR / "database" / "aiforge.db"

# ─── GitHub ──────────────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
# Legacy org/repo env vars kept for backward compatibility — not used in live mode
GITHUB_ORG  = os.getenv("GITHUB_ORG", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

# ── Copilot public launch date — the Before/After AI boundary ──
COPILOT_LAUNCH_DATE = date(2022, 6, 21)

# ── 15 public repos mapped to 7 departments ──────────────
# Format: "owner/repo": "Department"
# Chosen for: volume (1k+ PRs), activity post-2021, diverse engineering culture
TARGET_REPOS: dict[str, str] = {
    # Engineering — core systems & IDEs
    "microsoft/vscode":            "Engineering",
    "microsoft/TypeScript":        "Engineering",
    "electron/electron":           "Engineering",

    # Frontend — UI frameworks
    "facebook/react":              "Frontend",
    "vuejs/core":                  "Frontend",
    "angular/angular":             "Frontend",

    # Backend — server frameworks
    "django/django":               "Backend",
    "fastapi/fastapi":             "Backend",
    "expressjs/express":           "Backend",

    # DevOps — infra & orchestration
    "kubernetes/kubernetes":       "DevOps",
    "docker/compose":              "DevOps",
    "hashicorp/terraform":         "DevOps",

    # Data Science — ML & analytics
    "scikit-learn/scikit-learn":   "Data Science",
    "pandas-dev/pandas":           "Data Science",
    "pytorch/pytorch":             "Data Science",

    # Security — vulnerability & scanning tools
    "OWASP/CheatSheetSeries":      "Security",
    "anchore/grype":               "Security",

    # Mobile — cross-platform frameworks
    "flutter/flutter":             "Mobile",
    "facebook/react-native":       "Mobile",
}

# Derived: department list (alphabetical, deduplicated)
DEPARTMENTS: list[str] = sorted(set(TARGET_REPOS.values()))

# Repo → department lookup (reverse of TARGET_REPOS, by repo name only)
REPO_TO_DEPT: dict[str, str] = {
    repo.split("/")[1]: dept
    for repo, dept in TARGET_REPOS.items()
}

# Max PRs fetched per repo during a live sync
MAX_PRS_PER_REPO = 400   # 19 repos × 400 = up to 7,600 PRs total
# How many days back to look (covers well past Copilot launch)
GITHUB_DAYS_BACK = 1200  # ~3.3 years — captures Before + After Copilot

# ─── OpenAI ──────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_ORG_ID  = os.getenv("OPENAI_ORG_ID",  "")

# ─── App Settings ────────────────────────────────────────
APP_ENV   = os.getenv("APP_ENV",            "development")
LOG_LEVEL = os.getenv("LOG_LEVEL",          "INFO")
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "600"))

# ─── Analytics constants ─────────────────────────────────
MODEL_COST_PER_1K_TOKENS: dict[str, float] = {
    "gpt-4.1-mini": 0.004,
    "gpt-4.1": 0.020,
    "claude-sonnet-4": 0.015,
    "claude-haiku-3.5": 0.003,
    "gemini-2.5-pro": 0.008,
    "github-copilot": 0.010,
    "llama-3.3-70b": 0.002,
    "unknown":         0.003,
}

RISK_WEIGHTS = {
    "pii_entities_found":    40,
    "high_sensitivity_word": 20,
    "prompt_length_factor":   5,
    "repeated_violations":   15,
}

RISK_THRESHOLDS = {
    "Critical": 75,
    "High":     50,
    "Medium":   25,
    "Low":       0,
}

# AI models used in synthetic usage log data
AI_MODELS = [
    "gpt-4.1-mini",
    "gpt-4.1",
    "claude-sonnet-4",
    "claude-haiku-3.5",
    "gemini-2.5-pro",
    "github-copilot",
    "llama-3.3-70b"
]

# Roles per department — aligned to DEPARTMENTS
ROLES_BY_DEPT: dict[str, list[str]] = {
    "Engineering":  ["Senior Engineer",    "Staff Engineer",    "Engineering Manager"],
    "Frontend":     ["Frontend Engineer",  "UI/UX Engineer",    "Frontend Lead"],
    "Backend":      ["Backend Engineer",   "API Specialist",    "Backend Lead"],
    "DevOps":       ["DevOps Engineer",    "SRE",               "Platform Lead"],
    "Data Science": ["Data Scientist",     "ML Engineer",       "Analytics Lead"],
    "Security":     ["Security Engineer",  "AppSec Analyst",    "Security Lead"],
    "Mobile":       ["Mobile Engineer",    "iOS Engineer",      "Android Engineer"],
}

# Cycle time parameters per department for synthetic Jira data
# (before_mean_hrs, before_std, after_mean_hrs, after_std)
CYCLE_TIME_PARAMS: dict[str, tuple] = {
    "Engineering":  (48,  20, 30, 12),
    "Frontend":     (40,  18, 26, 10),
    "Backend":      (56,  22, 36, 14),
    "DevOps":       (32,  14, 20,  8),
    "Data Science": (72,  30, 46, 18),
    "Security":     (60,  25, 42, 16),
    "Mobile":       (52,  22, 34, 14),
}

# Synthetic data volumes
SYNTHETIC_USERS   = 100   # Increased to cover 7 departments
SYNTHETIC_LOGS    = 8000  # Increased to provide more robust analytics
SYNTHETIC_TICKETS = 3500

# Data directory shortcuts
DATA_DIR      = ROOT_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SYNTHETIC_DIR = DATA_DIR / "synthetic"

# ─── Logger ──────────────────────────────────────────────
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level=LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
)
