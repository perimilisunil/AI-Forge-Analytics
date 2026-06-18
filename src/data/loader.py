"""
src/data/loader.py
──────────────────
Unified data loader. Reads from SQLite or CSV fallback.
All other modules import from here — never open DB connections directly.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.config import DB_PATH, SYNTHETIC_DIR


# ─── Core loader ─────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Run: python scripts/setup_db.py"
        )
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Execute a SQL query and return a DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


# ─── Table loaders ───────────────────────────────────────

def load_users() -> pd.DataFrame:
    logger.info("Loading users_master")
    df = query("SELECT * FROM users_master")
    return df


def load_usage_logs(department: str = None) -> pd.DataFrame:
    logger.info("Loading ai_usage_logs")
    if department and department != "All":
        df = query(
            "SELECT * FROM ai_usage_logs WHERE department = ?",
            (department,)
        )
    else:
        df = query("SELECT * FROM ai_usage_logs")
    # Type coercion
    for col in ["token_count", "cost_usd", "risk_score", "risk_flag"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def load_jira(department: str = None) -> pd.DataFrame:
    logger.info("Loading jira_tickets_synthetic")
    if department and department != "All":
        df = query(
            "SELECT * FROM jira_tickets_synthetic WHERE department = ?",
            (department,)
        )
    else:
        df = query("SELECT * FROM jira_tickets_synthetic")
    for col in ["cycle_time_hours", "story_points",
                "avg_ticket_resolution_hours", "jira_tickets_closed"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["created_at"]  = pd.to_datetime(df["created_at"],  errors="coerce")
    df["resolved_at"] = pd.to_datetime(df["resolved_at"], errors="coerce")
    return df


def load_github(department: str = None) -> pd.DataFrame:
    """
    Load github_metrics table.
    Includes period column (Before/After Copilot launch),
    repo_full_name, and all numeric/datetime coercions.
    """
    logger.info("Loading github_metrics")
    try:
        if department and department != "All":
            df = query(
                "SELECT * FROM github_metrics WHERE department = ?",
                (department,)
            )
        else:
            df = query("SELECT * FROM github_metrics")

        if df.empty:
            return df

        # Numeric coercion
        for col in ["cycle_time_hours", "lines_added", "lines_removed",
                    "review_count", "commit_count", "rework_ratio"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Datetime parsing
        for col in ["created_at", "merged_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

        # Guarantee period column exists and is valid
        if "period" not in df.columns:
            df["period"] = "Unknown"
        df["period"] = df["period"].fillna("Unknown")

        # Guarantee repo_full_name exists (backfill from repo_name if missing)
        if "repo_full_name" not in df.columns:
            df["repo_full_name"] = df.get("repo_name", "unknown/unknown")

        logger.info(
            f"github_metrics loaded — {len(df):,} rows | "
            f"Before: {(df['period']=='Before').sum():,} | "
            f"After: {(df['period']=='After').sum():,}"
        )
        return df

    except Exception as exc:
        logger.warning(f"github_metrics table empty or missing: {exc} — returning empty DataFrame")
        return pd.DataFrame()


def load_analytics_cache() -> pd.DataFrame:
    logger.info("Loading analytics_cache")
    try:
        return query("SELECT * FROM analytics_cache")
    except Exception:
        return pd.DataFrame()


# ─── Parquet fallback ────────────────────────────────────────

def load_parquet_fallback(filename: str) -> pd.DataFrame:
    path = SYNTHETIC_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Synthetic Parquet not found: {path}")
    return pd.read_parquet(path)