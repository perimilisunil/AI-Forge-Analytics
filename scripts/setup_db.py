"""
scripts/setup_db.py
────────────────────
One-command database setup:
  1. Creates all tables from schema.sql
  2. Generates synthetic users (one per department from TARGET_REPOS)
  3. Generates synthetic AI usage logs + Jira tickets
  4. Seeds a realistic synthetic github_metrics table
     (mirrors the real repo structure — replaced by live data after
      running:  python scripts/run_pipeline.py --mode live)
  5. Exports all tables to data/synthetic/ as CSVs

Run:  python scripts/setup_db.py
Re-run at any time to fully reset the database.
"""

import os
import sys
import sqlite3
import uuid
import random
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from src.config import (
    DB_PATH, DEPARTMENTS, AI_MODELS, ROLES_BY_DEPT,
    MODEL_COST_PER_1K_TOKENS, SYNTHETIC_DIR,
    SYNTHETIC_USERS, SYNTHETIC_LOGS, SYNTHETIC_TICKETS,
    TARGET_REPOS, REPO_TO_DEPT, COPILOT_LAUNCH_DATE,
    CYCLE_TIME_PARAMS, logger,
)

try:
    from faker import Faker
    fake = Faker()
    USE_FAKER = True
except ImportError:
    USE_FAKER = False
    logger.warning("faker not installed — using placeholder names")


# ─── Helpers ─────────────────────────────────────────────

def rdate(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def rid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12].upper()}"


PROMPT_TEMPLATES = [
    "Write unit tests for this function: {code}",
    "Summarise the following document: {doc}",
    "Help me debug this error: AttributeError in line 42",
    "Draft an email to the client about project delay",
    "Explain this SQL query: SELECT * FROM orders WHERE status='pending'",
    "Review this PR and suggest improvements",
    "Generate a regex to validate email addresses",
    "Write a Python script to parse JSON responses",
    "What is the best architecture for a microservice handling 10k rps?",
    "Translate this function to TypeScript",
    "My password is hunter2, can you check if this code is secure?",
    "Process card 4111-1111-1111-1111 for customer John Smith",
    "The SSN 123-45-6789 belongs to employee ID EMP001",
    "Email john.smith@acmecorp.com about the Q3 merger with ProjectPhoenix",
    "My API key sk-prod-abc123def456 is not working, please debug",
    "Generate a monthly report for the board",
    "Write acceptance criteria for this user story",
    "Optimise this database query for performance",
    "Create a data pipeline for real-time analytics",
    "Help me write documentation for this REST API",
    "Implement a binary search tree in Python",
    "Design a REST API for a social media platform",
    "Fix this memory leak in the following C++ code",
    "Explain how Kubernetes pod scheduling works",
    "Write a Terraform module for AWS ECS",
    "Debug this React component re-rendering issue",
    "Optimise this pandas DataFrame merge operation",
    "Write unit tests for this ML model evaluation pipeline",
    "Help me refactor this legacy Java code to use streams",
    "What are the security implications of storing JWT in localStorage?",
]

LICENCE_TYPES   = ["Enterprise", "Pro", "Free"]
LICENCE_WEIGHTS = [0.3, 0.5, 0.2]


# ═══════════════════════════════════════════════════════
# 1. INIT DATABASE
# ═══════════════════════════════════════════════════════

def init_db():
    # ── Create all required directories upfront ──────────
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    from src.config import RAW_DIR, PROCESSED_DIR, SYNTHETIC_DIR
    for folder, purpose in [
        (RAW_DIR,       "raw API responses"),
        (PROCESSED_DIR, "cleaned analysis-ready CSVs"),
        (SYNTHETIC_DIR, "auto-generated synthetic data"),
    ]:
        folder.mkdir(parents=True, exist_ok=True)
        # Write a README inside each folder so they're not empty
        readme = folder / "README.md"
        if not readme.exists():
            readme.write_text(f"# {folder.name}/\n{purpose.capitalize()}.\n")
        logger.info(f"  data/{folder.name}/ ready")

    # ── Apply schema ──────────────────────────────────────
    schema_path = ROOT / "database" / "schema.sql"
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    if schema_path.exists():
        cur.executescript(schema_path.read_text(encoding="utf-8"))
        logger.info(f"Schema applied from {schema_path}")
    conn.commit()
    conn.close()
    logger.info(f"Database initialised at {DB_PATH}")


# ═══════════════════════════════════════════════════════
# 2. GENERATE USERS
# ═══════════════════════════════════════════════════════

def generate_users(n: int) -> list[dict]:
    logger.info(f"Generating {n} users across {len(DEPARTMENTS)} departments")
    users = []
    adoption_start = datetime(2022, 1, 1)
    adoption_end   = datetime(2022, 10, 1)  # All adopted around Copilot launch

    # Ensure at least 3 users per department
    dept_pool = DEPARTMENTS * (n // len(DEPARTMENTS) + 1)

    for i in range(n):
        dept     = dept_pool[i] if i < len(dept_pool) else random.choice(DEPARTMENTS)
        role     = random.choice(ROLES_BY_DEPT.get(dept, ["Analyst"]))
        lic_type = random.choices(LICENCE_TYPES, weights=LICENCE_WEIGHTS)[0]
        name     = fake.name() if USE_FAKER else f"Employee_{i+1:03d}"

        # GitHub username — 85% of users have one (realistic)
        gh_user = None
        if random.random() > 0.15:
            gh_user = (
                fake.user_name().lower().replace(".", "_")
                if USE_FAKER else f"user_{i+1:03d}"
            )

        users.append({
            "user_id":           rid("USR"),
            "employee_name":     name,
            "department":        dept,
            "role":              role,
            "license_type":      lic_type,
            "hourly_rate":       round(random.uniform(35.0, 140.0), 2),
            "ai_adoption_date":  rdate(adoption_start, adoption_end).strftime("%Y-%m-%d"),
            "employment_status": random.choices(
                ["Active", "Inactive", "On-Leave"],
                weights=[85, 10, 5]
            )[0],
            "github_username": gh_user,
        })

    return users


# ═══════════════════════════════════════════════════════
# 3. GENERATE USAGE LOGS
# ═══════════════════════════════════════════════════════

def generate_usage_logs(users: list[dict], n: int) -> tuple:
    """Returns (logs, zombie_ids) so zombie_ids can be used in Jira generation."""
    logger.info(f"Generating {n} usage log entries")
    logs      = []
    log_start = datetime(2022, 6, 1)
    log_end   = datetime(2024, 6, 30)

    # ~15% of users are zombies: high spend, zero output
    zombie_ids = set(
        u["user_id"] for u in random.sample(users, max(1, len(users) // 7))
    )
    logger.info(f"  Zombie users designated: {len(zombie_ids)}")

    for _ in range(n):
        user      = random.choice(users)
        model = random.choices(AI_MODELS,weights=[22, 14, 18, 12, 12, 14, 8],k=1)[0]
        tokens = int(np.random.lognormal(mean=7.2,sigma=0.9))

        tokens = min(max(tokens, 100), 12000)
        cost_rate = MODEL_COST_PER_1K_TOKENS.get(model, 0.003)
        cost      = round((tokens / 1000) * cost_rate, 6)
        prompt_text = random.choice(PROMPT_TEMPLATES)

        # PII risk scoring
        risk_score = 0.0
        pii_kws    = ["password", "card", "ssn", "api key", "email",
                      "merger", "4111", "123-45", "sk-prod", "john.smith@"]
        risk_flag  = 0
        for kw in pii_kws:
            if kw.lower() in prompt_text.lower():
                risk_score += random.uniform(20, 35)
                risk_flag   = 1

        risk_score = min(round(risk_score + random.uniform(0, 15), 1), 100.0)
        if risk_score >= 75:   risk_level = "Critical"
        elif risk_score >= 50: risk_level = "High"
        elif risk_score >= 25: risk_level = "Medium"
        else:                  risk_level = "Low"

        # Zombies get inflated cost
        if user["user_id"] in zombie_ids:
            cost *= random.uniform(2, 4)
            tokens *= random.uniform(2, 3)

        logs.append({
            "prompt_id":   rid("LOG"),
            "user_id":     user["user_id"],
            "timestamp":   rdate(log_start, log_end).isoformat(),
            "department":  user["department"],
            "model_name":  model,
            "prompt_text": prompt_text[:500],
            "token_count": tokens,
            "cost_usd":    cost,
            "risk_flag":   risk_flag,
            "risk_score":  risk_score,
            "risk_level":  risk_level,
        })

    return logs, zombie_ids


# ═══════════════════════════════════════════════════════
# 4. GENERATE JIRA TICKETS
# ═══════════════════════════════════════════════════════

PRIORITIES    = ["Low", "Medium", "High", "Critical"]
PRIORITY_WGTS = [0.20, 0.45, 0.25, 0.10]


def generate_jira_tickets(users: list[dict], n_total: int,
                          zombie_ids: set = None) -> list[dict]:
    """
    Generate Before/After Jira tickets.
    Zombie users (zombie_ids) get jira_tickets_closed=0 in After period
    so the classifier can correctly identify them.
    """
    logger.info(f"Generating Jira tickets (target ~{n_total})")
    tickets   = []
    base_date = datetime(2021, 6, 1)
    zombie_ids = zombie_ids or set()

    for user in users:
        dept   = user["department"]
        params = CYCLE_TIME_PARAMS.get(dept, (56, 22, 36, 14))
        b_mean, b_std, a_mean, a_std = params
        is_zombie = user["user_id"] in zombie_ids

        n_before = random.randint(12, 22)
        n_after  = random.randint(15, 28)

        for _ in range(n_before):
            created  = rdate(base_date, base_date + timedelta(days=365))
            ct       = max(1.0, random.gauss(b_mean, b_std))
            resolved = created + timedelta(hours=ct)
            sp       = random.choices([1,2,3,5,8,13], weights=[5,20,30,25,15,5])[0]
            tickets.append({
                "jira_issue_id":               rid("JIRA"),
                "user_id":                     user["user_id"],
                "department":                  dept,
                "created_at":                  created.isoformat(),
                "resolved_at":                 resolved.isoformat(),
                "cycle_time_hours":            round(ct, 2),
                "story_points":                sp,
                "priority":                    random.choices(PRIORITIES, weights=PRIORITY_WGTS)[0],
                "period":                      "Before",
                "avg_ticket_resolution_hours": round(b_mean, 2),
                "jira_tickets_closed":         0,
            })

        for _ in range(n_after):
            created  = rdate(
                base_date + timedelta(days=400),
                base_date + timedelta(days=730)
            )
            ct       = max(0.5, random.gauss(a_mean, a_std))
            resolved = created + timedelta(hours=ct)
            sp       = random.choices([1,2,3,5,8,13], weights=[5,20,30,25,15,5])[0]

            # Zombies: high AI cost but zero ticket output
            if is_zombie:
                tickets_closed = 0
            else:
                tickets_closed = random.randint(1, sp + 1)

            tickets.append({
                "jira_issue_id":               rid("JIRA"),
                "user_id":                     user["user_id"],
                "department":                  dept,
                "created_at":                  created.isoformat(),
                "resolved_at":                 resolved.isoformat(),
                "cycle_time_hours":            round(ct, 2),
                "story_points":                sp,
                "priority":                    random.choices(PRIORITIES, weights=PRIORITY_WGTS)[0],
                "period":                      "After",
                "avg_ticket_resolution_hours": round(a_mean, 2),
                "jira_tickets_closed":         tickets_closed,
            })

    logger.info(
        f"  Generated {len(tickets)} tickets "
        f"(Before: {sum(1 for t in tickets if t['period']=='Before')}, "
        f"After: {sum(1 for t in tickets if t['period']=='After')})"
    )
    return tickets


# ═══════════════════════════════════════════════════════
# 5. GENERATE SYNTHETIC GITHUB METRICS
#    Mirrors the 19 real repos with plausible cycle times.
#    Replaced by live data after:  run_pipeline.py --mode live
# ═══════════════════════════════════════════════════════

# Realistic cycle time profiles per repo (Before_mean, After_mean, std)
REPO_PROFILES = {
    "vscode":            (38,  22, 20),
    "TypeScript":        (52,  34, 28),
    "electron":          (72,  48, 35),
    "react":             (44,  28, 22),
    "core":              (36,  24, 18),
    "angular":           (60,  40, 30),
    "django":            (80,  58, 38),
    "fastapi":           (24,  16, 12),
    "express":           (32,  22, 16),
    "kubernetes":        (18,  12, 10),
    "compose":           (28,  20, 14),
    "terraform":         (48,  32, 24),
    "scikit-learn":      (96,  68, 45),
    "pandas":            (88,  62, 40),
    "pytorch":           (72,  50, 35),
    "CheatSheetSeries":  (120, 90, 55),
    "grype":             (36,  24, 18),
    "flutter":           (56,  36, 26),
    "react-native":      (64,  44, 30),
}

COPILOT_CUTOFF = datetime(
    COPILOT_LAUNCH_DATE.year,
    COPILOT_LAUNCH_DATE.month,
    COPILOT_LAUNCH_DATE.day,
    tzinfo=timezone.utc,
)

SYNTHETIC_GH_USERNAMES = [
    "torvalds","gvanrossum","dhh","matz","antirez","jashkenas",
    "yyx990803","tj","rauchg","addyosmani","kentcdodds","sindresorhus",
    "nicolo-ribaudo","MarkPieszak","fkling","broofa","jonathantneal",
    "nicolo","feross","tannerlinsley","pmndrs","okonet","timdeschryver",
    "nicolo-","epoberezkin","gcanti","mattpocock","colinhacks","trpc",
    "alexdotjs","diegohaz","ardeois","meijer-dries","ndom91",
    "benawad","theprimeagen","fireship","academind","traversymedia",
]


def generate_github_metrics(n_per_repo: int = 120) -> list[dict]:
    """
    Generate synthetic PR data that mirrors the structure of the 19 real repos.
    Before period: PRs from Jan 2020 – Jun 2022
    After period:  PRs from Jun 2022 – Dec 2023
    """
    logger.info(
        f"Generating synthetic GitHub metrics "
        f"({len(TARGET_REPOS)} repos × ~{n_per_repo} PRs)"
    )
    rows = []

    before_start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    before_end   = COPILOT_CUTOFF
    after_end    = datetime(2024, 1, 1, tzinfo=timezone.utc)

    for full_name, department in TARGET_REPOS.items():
        repo_name = full_name.split("/")[1]
        b_mean, a_mean, std = REPO_PROFILES.get(repo_name, (60, 42, 28))

        # ~50% Before, 50% After per repo
        n_before = n_per_repo // 2
        n_after  = n_per_repo - n_before

        for period, count, mean_hrs, t_start, t_end in [
            ("Before", n_before, b_mean, before_start, before_end),
            ("After",  n_after,  a_mean, COPILOT_CUTOFF, after_end),
        ]:
            for _ in range(count):
                created_dt = rdate(
                    t_start.replace(tzinfo=None),
                    t_end.replace(tzinfo=None)
                ).replace(tzinfo=timezone.utc)
                ct = max(0.5, random.gauss(mean_hrs, std))
                merged_dt  = created_dt + timedelta(hours=ct)

                additions  = random.randint(10,  2000)
                deletions  = random.randint(0,   additions)
                pr_num     = random.randint(1000, 99999)
                gh_user    = random.choice(SYNTHETIC_GH_USERNAMES)

                rows.append({
                    "pr_id":            f"{repo_name}#{pr_num}",
                    "user_id":          None,
                    "github_username":  gh_user,
                    "repo_name":        repo_name,
                    "repo_full_name":   full_name,
                    "department":       department,
                    "pr_title":         f"fix: update {repo_name} component #{pr_num}",
                    "pr_state":         "merged",
                    "created_at":       created_dt.isoformat(),
                    "merged_at":        merged_dt.isoformat(),
                    "cycle_time_hours": round(ct, 2),
                    "lines_added":      additions,
                    "lines_removed":    deletions,
                    "review_count":     random.randint(0, 8),
                    "commit_count":     random.randint(1, 12),
                    "rework_ratio":     round(deletions / max(additions, 1), 3),
                    "period":           period,
                })

    logger.info(f"  Generated {len(rows):,} synthetic GitHub PR rows")
    return rows


# ═══════════════════════════════════════════════════════
# 6. WRITE TO DB AND EXPORT CSVs
# ═══════════════════════════════════════════════════════

def write_to_db(users, logs, tickets, github_rows):
    import pandas as pd
    conn = sqlite3.connect(DB_PATH)

    pd.DataFrame(users).to_sql(
        "users_master", conn, if_exists="replace", index=False)
    logger.info(f"  users_master:          {len(users):>6} rows")

    pd.DataFrame(logs).to_sql(
        "ai_usage_logs", conn, if_exists="replace", index=False)
    logger.info(f"  ai_usage_logs:         {len(logs):>6} rows")

    pd.DataFrame(tickets).to_sql(
        "jira_tickets_synthetic", conn, if_exists="replace", index=False)
    logger.info(f"  jira_tickets_synthetic:{len(tickets):>6} rows")

    pd.DataFrame(github_rows).to_sql(
        "github_metrics", conn, if_exists="replace", index=False)
    logger.info(f"  github_metrics:        {len(github_rows):>6} rows")

    conn.close()


def export_csvs(users, logs, tickets, github_rows):
    import pandas as pd
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(users).to_csv(SYNTHETIC_DIR / "user_mapping.csv",    index=False)
    pd.DataFrame(logs).to_csv( SYNTHETIC_DIR / "ai_usage.csv",        index=False)
    pd.DataFrame(tickets).to_csv(SYNTHETIC_DIR / "jira_tickets.csv",   index=False)
    pd.DataFrame(github_rows).to_csv(SYNTHETIC_DIR / "github_prs.csv", index=False)
    logger.info(f"  CSVs exported to {SYNTHETIC_DIR}")


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    random.seed(42)

    logger.info("══════════════════════════════════════════════")
    logger.info("  AIFORGE — Database Setup & Seeding")
    logger.info(f"  Departments: {', '.join(DEPARTMENTS)}")
    logger.info(f"  Repos: {len(TARGET_REPOS)}")
    logger.info(f"  Copilot boundary: {COPILOT_LAUNCH_DATE}")
    logger.info("══════════════════════════════════════════════")

    init_db()

    users       = generate_users(SYNTHETIC_USERS)
    logs, zombie_ids = generate_usage_logs(users, SYNTHETIC_LOGS)
    tickets     = generate_jira_tickets(users, SYNTHETIC_TICKETS, zombie_ids)
    github_rows = generate_github_metrics(n_per_repo=120)

    logger.info("\nWriting to database…")
    write_to_db(users, logs, tickets, github_rows)

    logger.info("\nExporting CSVs…")
    export_csvs(users, logs, tickets, github_rows)

    logger.info("\n══════════════════════════════════════════════")
    logger.info("  Setup complete!")
    logger.info("  Next steps:")
    logger.info("  1. streamlit run app/main.py          ← launch dashboard")
    logger.info("  2. Add GITHUB_TOKEN to .env")
    logger.info("  3. python scripts/run_pipeline.py --mode live  ← fetch real PRs")
    logger.info("══════════════════════════════════════════════")
