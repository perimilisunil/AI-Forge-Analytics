"""
src/analysis/metrics.py
────────────────────────
Core Analytics Engine.
Computes:
  - Net ROI per user and per department
  - Department risk scores
  - Efficiency delta (Before/After AI)
  - Monthly value saved
  - Analytics cache population
"""

import sqlite3
import uuid
from datetime import datetime

import numpy as np
import pandas as pd
from loguru import logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.config import DB_PATH, RISK_THRESHOLDS


# ─── ROI Calculation ─────────────────────────────────────

def calculate_user_roi(
    avg_cycle_before: float,
    avg_cycle_after:  float,
    tickets_closed:   int,
    hourly_rate:      float,
    total_ai_cost:    float,
) -> dict:
    """
    Calculate Net ROI for a single user.

    Formula:
        hours_saved = max(0, before_avg − after_avg)
        dollar_saved = hours_saved × tickets_closed × hourly_rate
        net_roi = dollar_saved − total_ai_cost
        pct_improvement = hours_saved / before_avg × 100
    """
    hours_saved = max(0.0, avg_cycle_before - avg_cycle_after)

    dollar_saved = hours_saved * tickets_closed * hourly_rate

    net_roi = dollar_saved - total_ai_cost

    pct_improvement = (
        (hours_saved / avg_cycle_before * 100)
        if avg_cycle_before > 0 else 0.0
    )

    return {
        "hours_saved_per_ticket": round(hours_saved, 2),
        "dollar_value_saved":     round(dollar_saved, 2),
        "net_roi":                round(net_roi, 2),
        "pct_improvement":        round(pct_improvement, 1),
        "roi_positive":           net_roi > 0,
    }


def calculate_dept_risk_score(risk_scores: pd.Series) -> float:
    """
    Compute a department-level risk score (0–100).
    Uses 80th percentile to avoid outliers dominating.
    """
    if risk_scores.empty or risk_scores.sum() == 0:
        return 0.0
    p80 = float(np.percentile(risk_scores[risk_scores > 0], 80))
    return round(min(p80, 100.0), 1)


def risk_score_to_level(score: float) -> str:
    for level, threshold in RISK_THRESHOLDS.items():
        if score >= threshold:
            return level
    return "Low"


# ─── Monthly Analytics Cache ─────────────────────────────

def populate_analytics_cache(
    user_summary: pd.DataFrame,
    logs: pd.DataFrame,
) -> int:
    """
    Write pre-computed monthly metrics to analytics_cache table.
    Returns number of rows written.
    """
    if user_summary.empty:
        logger.warning("User summary is empty — skipping cache population")
        return 0

    rows = []
    now  = datetime.utcnow().isoformat()

    # Group logs by user + month
    if "month_year" not in logs.columns:
        logs = logs.copy()
        logs["month_year"] = pd.to_datetime(
            logs["timestamp"], errors="coerce"
        ).dt.to_period("M").astype(str)

    monthly_cost = (
        logs.groupby(["user_id", "month_year"])
        .agg(total_cost=("cost_usd", "sum"),
             total_tokens=("token_count", "sum"),
             pii_violations=("risk_flag", "sum"))
        .reset_index()
    )

    for _, row in user_summary.iterrows():
        uid  = row["user_id"]
        dept = row.get("department", "")

        user_monthly = monthly_cost[monthly_cost["user_id"] == uid]

        for _, mrow in user_monthly.iterrows():
            roi = calculate_user_roi(
                avg_cycle_before = float(row.get("avg_cycle_before", 0)),
                avg_cycle_after  = float(row.get("avg_cycle_after",  0)),
                tickets_closed   = int(row.get("tickets_closed", 0)),
                hourly_rate      = float(row.get("hourly_rate", 0)),
                total_ai_cost    = float(mrow.get("total_cost", 0)),
            )

            rows.append({
                "cache_id":             str(uuid.uuid4()),
                "user_id":              uid,
                "department":           dept,
                "month_year":           mrow["month_year"],
                "total_ai_cost":        mrow.get("total_cost", 0),
                "total_tokens":         int(mrow.get("total_tokens", 0)),
                "tickets_before_avg":   row.get("avg_cycle_before", 0),
                "tickets_after_avg":    row.get("avg_cycle_after",  0),
                "hours_saved":          roi["hours_saved_per_ticket"],
                "dollar_value_saved":   roi["dollar_value_saved"],
                "net_roi":              roi["net_roi"],
                "dept_risk_score":      0.0,  # Filled in second pass
                "pii_violations":       int(mrow.get("pii_violations", 0)),
                "computed_at":          now,
            })

    if not rows:
        return 0

    cache_df = pd.DataFrame(rows)

    # Second pass: fill dept_risk_score
    if not logs.empty and "risk_score" in logs.columns:
        dept_risk = (
            logs.groupby("department")["risk_score"]
            .apply(calculate_dept_risk_score)
            .reset_index()
            .rename(columns={"risk_score": "dept_risk_score"})
        )
        cache_df = cache_df.merge(
            dept_risk, on="department", how="left", suffixes=("_old", "")
        )
        if "dept_risk_score_old" in cache_df.columns:
            cache_df.drop(columns=["dept_risk_score_old"], inplace=True)

    # Write to DB
    conn = sqlite3.connect(DB_PATH)
    try:
        cache_df.to_sql(
            "analytics_cache", conn,
            if_exists="replace", index=False
        )
        logger.info(f"Analytics cache populated: {len(cache_df)} rows")
    finally:
        conn.close()

    return len(cache_df)


# ─── Summary stats helpers ───────────────────────────────

def executive_kpis(logs: pd.DataFrame, jira: pd.DataFrame,
                   user_summary: pd.DataFrame) -> dict:
    """
    Compute the 5 headline KPIs for the executive strip.
    """
    total_spend = logs["cost_usd"].sum() if not logs.empty else 0

    before_avg = jira[jira["period"] == "Before"]["cycle_time_hours"].mean() if not jira.empty else 0
    after_avg  = jira[jira["period"] == "After" ]["cycle_time_hours"].mean() if not jira.empty else 0
    pct_imp    = ((before_avg - after_avg) / before_avg * 100) if before_avg > 0 else 0

    total_tokens = int(logs["token_count"].sum()) if not logs.empty else 0

    high_risk = int(
        len(logs[logs["risk_level"].isin(["High", "Critical"])])
        if not logs.empty else 0
    )

    github_matched = int(
        user_summary["github_username"].notna().sum()
        if "github_username" in user_summary.columns else 0
    )

    return {
        "total_spend":      round(total_spend, 2),
        "pct_improvement":  round(pct_imp, 1),
        "total_tokens":     total_tokens,
        "high_risk_events": high_risk,
        "github_matched":   github_matched,
    }
