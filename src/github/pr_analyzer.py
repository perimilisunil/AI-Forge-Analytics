"""
src/github/pr_analyzer.py
──────────────────────────
PR-level analytics for public-repo data.

Key change from v1: period labelling is now done during fetch
(in api_client.py using COPILOT_LAUNCH_DATE), so label_pr_period()
here simply validates/backfills rows that might be missing the column.

All analysis functions work on the github_metrics DataFrame schema.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from loguru import logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.config import COPILOT_LAUNCH_DATE, TARGET_REPOS, DEPARTMENTS


# ─── Period validation / backfill ────────────────────────

def ensure_period_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Guarantee every row has a 'period' column (Before / After).
    The fetch layer already sets this; this function is a safety net
    for rows loaded from the DB or CSV that might pre-date the column.
    """
    if df.empty:
        return df

    df = df.copy()
    cutoff = datetime(
        COPILOT_LAUNCH_DATE.year,
        COPILOT_LAUNCH_DATE.month,
        COPILOT_LAUNCH_DATE.day,
        tzinfo=timezone.utc,
    )

    if "period" not in df.columns:
        df["period"] = "Unknown"

    # Backfill rows where period is missing / null
    merged = pd.to_datetime(df.get("merged_at", pd.NaT), errors="coerce", utc=True)
    mask   = df["period"].isnull() | (df["period"] == "Unknown")
    df.loc[mask & (merged >= cutoff), "period"] = "After"
    df.loc[mask & (merged <  cutoff), "period"] = "Before"
    df.loc[mask & merged.isna(),      "period"] = "Unknown"

    return df


# ─── Department enrichment ────────────────────────────────

def enrich_department(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill missing 'department' values using REPO_TO_DEPT lookup.
    Handles both 'repo_name' (short) and 'repo_full_name' (owner/repo).
    """
    from src.config import REPO_TO_DEPT
    if df.empty or "department" not in df.columns:
        return df
    df = df.copy()
    mask = df["department"].isna() | (df["department"] == "")
    if mask.any() and "repo_name" in df.columns:
        df.loc[mask, "department"] = df.loc[mask, "repo_name"].map(REPO_TO_DEPT)
    return df


# ─── Core analytics ───────────────────────────────────────

def pr_performance_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-department × period summary statistics.
    This is the primary table used by the Productivity tab.
    """
    if df.empty:
        return pd.DataFrame()

    df = ensure_period_column(df)
    df = df[df["period"].isin(["Before", "After"])]

    summary = (
        df.groupby(["department", "period"])
        .agg(
            pr_count=("pr_id",            "count"),
            avg_cycle_hours=("cycle_time_hours", "mean"),
            median_cycle_hours=("cycle_time_hours", "median"),
            p90_cycle_hours=(
                "cycle_time_hours",
                lambda x: float(np.percentile(x, 90)) if len(x) else 0,
            ),
            avg_rework_ratio=("rework_ratio",   "mean"),
            avg_review_count=("review_count",   "mean"),
            avg_commits=("commit_count",    "mean"),
            total_lines_added=("lines_added",    "sum"),
            total_lines_removed=("lines_removed",  "sum"),
            unique_contributors=("github_username", "nunique"),
        )
        .round(2)
        .reset_index()
    )
    return summary


def compute_pr_efficiency_delta(summary: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Before → After delta per department.
    Returns one row per department with cycle time improvement metrics.
    """
    if summary.empty:
        return pd.DataFrame()

    before = (
        summary[summary["period"] == "Before"]
        .set_index("department")[["avg_cycle_hours", "median_cycle_hours",
                                   "avg_rework_ratio", "pr_count"]]
        .rename(columns={
            "avg_cycle_hours":    "before_avg",
            "median_cycle_hours": "before_median",
            "avg_rework_ratio":   "before_rework",
            "pr_count":           "before_prs",
        })
    )
    after = (
        summary[summary["period"] == "After"]
        .set_index("department")[["avg_cycle_hours", "median_cycle_hours",
                                   "avg_rework_ratio", "pr_count",
                                   "unique_contributors"]]
        .rename(columns={
            "avg_cycle_hours":    "after_avg",
            "median_cycle_hours": "after_median",
            "avg_rework_ratio":   "after_rework",
            "pr_count":           "after_prs",
            "unique_contributors":"contributors",
        })
    )

    delta = pd.concat([before, after], axis=1).fillna(0).reset_index()
    delta.rename(columns={"index": "department"}, inplace=True)

    delta["hours_saved"] = (
        delta["before_avg"] - delta["after_avg"]
    ).clip(lower=0)

    delta["pct_improvement"] = (
        delta["hours_saved"]
        / delta["before_avg"].replace(0, np.nan) * 100
    ).fillna(0).round(1)

    delta["rework_improvement_pct"] = (
        (delta["before_rework"] - delta["after_rework"])
        / delta["before_rework"].replace(0, np.nan) * 100
    ).fillna(0).round(1)

    return delta.sort_values("pct_improvement", ascending=False)


def top_contributors(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """
    Top N contributors ranked by total PRs merged, with per-period split.
    """
    if df.empty:
        return pd.DataFrame()

    return (
        df[df["pr_state"] == "merged"]
        .groupby(["github_username", "department"])
        .agg(
            total_prs=("pr_id",            "count"),
            avg_cycle=("cycle_time_hours", "mean"),
            avg_rework=("rework_ratio",    "mean"),
            total_lines=("lines_added",    "sum"),
            repos=("repo_name",            "nunique"),
        )
        .round(2)
        .reset_index()
        .nlargest(n, "total_prs")
        .reset_index(drop=True)
    )


def repo_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-repo statistics — useful for the GitHub deep-dive view.
    """
    if df.empty:
        return pd.DataFrame()

    return (
        df.groupby(["repo_name", "department", "period"])
        .agg(
            pr_count=("pr_id",            "count"),
            avg_cycle=("cycle_time_hours", "mean"),
            avg_rework=("rework_ratio",    "mean"),
            contributors=("github_username", "nunique"),
        )
        .round(2)
        .reset_index()
        .sort_values(["department", "repo_name", "period"])
    )


def velocity_trend_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Month-by-month PR velocity across all repos.
    Shows the adoption curve around the Copilot launch date.
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["month"] = pd.to_datetime(
        df["merged_at"], errors="coerce", utc=True
    ).dt.to_period("M").astype(str)

    monthly = (
        df.groupby(["month", "department"])
        .agg(
            pr_count=("pr_id",            "count"),
            avg_cycle=("cycle_time_hours", "mean"),
            avg_rework=("rework_ratio",    "mean"),
        )
        .round(2)
        .reset_index()
        .sort_values("month")
    )
    return monthly
