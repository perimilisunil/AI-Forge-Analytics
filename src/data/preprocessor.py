"""
src/data/preprocessor.py
─────────────────────────
Data cleaning, type enforcement, and feature engineering.
All derived columns are computed here — dashboards call this, not raw loaders.
"""

import numpy as np
import pandas as pd
from loguru import logger


def enrich_usage_logs(logs: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    """
    Merge usage logs with user metadata; add time-based features.
    Returns enriched DataFrame ready for analytics.
    """
    logger.info(f"Enriching {len(logs):,} usage log rows")

    # Merge user metadata
    user_cols = ["user_id", "employee_name", "department", "role",
                 "license_type", "hourly_rate", "github_username"]
    user_cols = [c for c in user_cols if c in users.columns]

    enriched = logs.merge(
        users[user_cols],
        on="user_id",
        how="left",
        suffixes=("", "_user")
    )

    # Overwrite department from user master if missing in log
    if "department_user" in enriched.columns:
        enriched["department"] = enriched["department"].fillna(
            enriched["department_user"]
        )
        enriched.drop(columns=["department_user"], inplace=True)

    # Time features
    if "timestamp" in enriched.columns:
        enriched["date"]       = enriched["timestamp"].dt.date
        enriched["hour"]       = enriched["timestamp"].dt.hour
        enriched["day_name"]   = enriched["timestamp"].dt.day_name()
        enriched["week"]       = enriched["timestamp"].dt.isocalendar().week.astype(int)
        enriched["month_year"] = enriched["timestamp"].dt.to_period("M").astype(str)

    logger.info("Usage log enrichment complete")
    return enriched


def compute_dept_performance(jira: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Before/After cycle time statistics per department.
    Returns one row per department with efficiency metrics.
    """
    before = (
        jira[jira["period"] == "Before"]
        .groupby("department")["cycle_time_hours"]
        .agg(before_mean="mean", before_median="median", before_count="count")
        .reset_index()
    )
    after = (
        jira[jira["period"] == "After"]
        .groupby("department")["cycle_time_hours"]
        .agg(after_mean="mean", after_median="median", after_count="count")
        .reset_index()
    )
    perf = before.merge(after, on="department", how="outer")
    perf["hours_saved_mean"]   = (perf["before_mean"]   - perf["after_mean"]  ).clip(lower=0)
    perf["hours_saved_median"] = (perf["before_median"] - perf["after_median"]).clip(lower=0)
    perf["pct_improvement"]    = (
        perf["hours_saved_mean"] / perf["before_mean"].replace(0, np.nan) * 100
    ).fillna(0).round(1)
    return perf


def compute_user_summary(
    logs: pd.DataFrame,
    jira: pd.DataFrame,
    users: pd.DataFrame,
    github: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Build a per-user summary table combining:
    - AI spend and token usage
    - Jira productivity (Before / After)
    - GitHub PR metrics
    - Zombie user classification
    - Net ROI
    """
    logger.info("Computing per-user summary")

    # AI cost per user
    cost_agg = (
        logs.groupby("user_id")
        .agg(total_cost=("cost_usd", "sum"),
             total_tokens=("token_count", "sum"),
             prompt_count=("prompt_id", "count"))
        .reset_index()
    )

    # Jira Before average
    jira_before = (
        jira[jira["period"] == "Before"]
        .groupby("user_id")["cycle_time_hours"]
        .mean()
        .reset_index()
        .rename(columns={"cycle_time_hours": "avg_cycle_before"})
    )

    # Jira After: average cycle time + tickets closed
    jira_after = (
        jira[jira["period"] == "After"]
        .groupby("user_id")
        .agg(avg_cycle_after=("cycle_time_hours", "mean"),
             tickets_closed=("jira_tickets_closed", "sum"))
        .reset_index()
    )

    # Build summary
    summary = users.copy()
    summary = summary.merge(cost_agg,    on="user_id", how="left")
    summary = summary.merge(jira_before, on="user_id", how="left")
    summary = summary.merge(jira_after,  on="user_id", how="left")

    # Fill nulls
    for col in ["total_cost", "total_tokens", "prompt_count",
                "avg_cycle_before", "avg_cycle_after", "tickets_closed"]:
        if col in summary.columns:
            summary[col] = summary[col].fillna(0)

    # GitHub PR metrics
    if github is not None and not github.empty and "user_id" in github.columns:
        gh_agg = (
            github[github["pr_state"] == "merged"]
            .groupby("user_id")
            .agg(prs_merged=("pr_id", "count"),
                 avg_pr_cycle=("cycle_time_hours", "mean"),
                 avg_rework=("rework_ratio", "mean"))
            .reset_index()
        )
        summary = summary.merge(gh_agg, on="user_id", how="left")
        summary[["prs_merged", "avg_pr_cycle", "avg_rework"]] = (
            summary[["prs_merged", "avg_pr_cycle", "avg_rework"]].fillna(0)
        )
    else:
        summary["prs_merged"]  = 0
        summary["avg_pr_cycle"] = 0.0
        summary["avg_rework"]   = 0.0

    # Derived metrics
    summary["hours_saved_per_ticket"] = (
        summary["avg_cycle_before"] - summary["avg_cycle_after"]
    ).clip(lower=0)

    hourly = summary.get("hourly_rate", pd.Series(0, index=summary.index))
    summary["dollar_value_saved"] = (
        summary["hours_saved_per_ticket"] * summary["tickets_closed"] * hourly
    ).fillna(0)

    summary["net_roi"] = (summary["dollar_value_saved"] - summary["total_cost"]).fillna(0)

    summary["pct_improvement"] = (
        summary["hours_saved_per_ticket"]
        / summary["avg_cycle_before"].replace(0, np.nan) * 100
    ).fillna(0).round(1)

    # Zombie classification:
    # High cost + no tickets closed + no PRs merged
    median_cost = summary["total_cost"].median()
    summary["is_zombie"] = (
        (summary["total_cost"] > median_cost) &
        (summary["tickets_closed"] == 0) &
        (summary["prs_merged"] == 0) &
        (summary["total_cost"] > 0)
    ).astype(int)

    logger.info(f"User summary computed — {len(summary)} users, "
                f"{summary['is_zombie'].sum()} zombies identified")
    return summary


# ─── Save to disk ─────────────────────────────────────────

def save_processed(
    enriched:     "pd.DataFrame",
    dept_perf:    "pd.DataFrame",
    user_summary: "pd.DataFrame",
    github_df:    "pd.DataFrame | None" = None,
) -> None:
    """
    Write all processed DataFrames to data/processed/ as parquets.
    Call this after compute_user_summary() to make outputs visible on disk.

    Files written:
        data/processed/usage_logs_enriched.parquet   ← enriched logs with time features
        data/processed/dept_performance.parquet       ← Before/After dept stats
        data/processed/user_summary.parquet           ← per-user ROI + zombie flag
        data/processed/github_pr_enriched.parquet     ← GitHub PRs (if provided)
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.config import PROCESSED_DIR

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Redact prompt_text before saving to disk
    from src.governance.redactor import redact_dataframe
    safe_logs = redact_dataframe(enriched, text_col="prompt_text") \
        if "prompt_text" in enriched.columns else enriched

    safe_logs.to_parquet(PROCESSED_DIR / "usage_logs_enriched.parquet",  index=False)
    logger.info(f"Saved usage_logs_enriched.parquet  ({len(safe_logs):,} rows)")

    dept_perf.to_parquet(PROCESSED_DIR / "dept_performance.parquet",      index=False)
    logger.info(f"Saved dept_performance.parquet      ({len(dept_perf):,} rows)")

    user_summary.to_parquet(PROCESSED_DIR / "user_summary.parquet",       index=False)
    logger.info(f"Saved user_summary.parquet          ({len(user_summary):,} rows)")

    if github_df is not None and not github_df.empty:
        # Drop user_id to protect internal identity mapping
        gh_export = github_df.drop(columns=["user_id"], errors="ignore")
        gh_export.to_parquet(PROCESSED_DIR / "github_pr_enriched.parquet", index=False)
        logger.info(f"Saved github_pr_enriched.parquet    ({len(gh_export):,} rows)")

    logger.info(f"All processed files → {PROCESSED_DIR}")
