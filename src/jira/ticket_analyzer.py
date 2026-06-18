"""
src/jira/ticket_analyzer.py
────────────────────────────
Jira ticket analytics: cycle time, throughput, velocity shift.
Core of the Before/After AI productivity measurement.
"""

import numpy as np
import pandas as pd
from loguru import logger


def compute_cycle_time(jira_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute cycle_time_hours from created_at → resolved_at
    for any rows where it is missing (zero or NaN).
    """
    df = jira_df.copy()
    mask = df["cycle_time_hours"] == 0
    if mask.any():
        delta = (
            pd.to_datetime(df.loc[mask, "resolved_at"], errors="coerce") -
            pd.to_datetime(df.loc[mask, "created_at"],  errors="coerce")
        ).dt.total_seconds() / 3600
        df.loc[mask, "cycle_time_hours"] = delta.fillna(0).clip(lower=0)
    return df


def velocity_analysis(jira_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute sprint-level velocity: story points per period per department.
    """
    if jira_df.empty:
        return pd.DataFrame()

    velocity = (
        jira_df.groupby(["department", "period"])
        .agg(
            total_tickets=("jira_issue_id", "count"),
            total_story_points=("story_points", "sum"),
            avg_cycle_hours=("cycle_time_hours", "mean"),
            median_cycle_hours=("cycle_time_hours", "median"),
            p90_cycle_hours=(
                "cycle_time_hours",
                lambda x: np.percentile(x, 90) if len(x) else 0
            ),
        )
        .reset_index()
    )

    for col in ["avg_cycle_hours", "median_cycle_hours", "p90_cycle_hours"]:
        velocity[col] = velocity[col].round(2)

    return velocity


def priority_breakdown(jira_df: pd.DataFrame) -> pd.DataFrame:
    """
    Count tickets by priority × period × department.
    """
    if jira_df.empty:
        return pd.DataFrame()

    return (
        jira_df.groupby(["department", "priority", "period"])
        ["jira_issue_id"].count()
        .reset_index()
        .rename(columns={"jira_issue_id": "ticket_count"})
    )


def compute_throughput_delta(velocity: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Before → After throughput improvement per department.
    """
    if velocity.empty:
        return pd.DataFrame()

    before = velocity[velocity["period"] == "Before"].set_index("department")
    after  = velocity[velocity["period"] == "After" ].set_index("department")

    delta = pd.DataFrame(index=before.index.union(after.index))
    delta["before_cycle"]  = before.get("avg_cycle_hours",      pd.Series(dtype=float))
    delta["after_cycle"]   = after.get("avg_cycle_hours",       pd.Series(dtype=float))
    delta["before_points"] = before.get("total_story_points",   pd.Series(dtype=float))
    delta["after_points"]  = after.get("total_story_points",    pd.Series(dtype=float))
    delta = delta.fillna(0).reset_index()
    delta.rename(columns={"index": "department"}, inplace=True)

    delta["cycle_improvement_pct"] = (
        (delta["before_cycle"] - delta["after_cycle"])
        / delta["before_cycle"].replace(0, np.nan) * 100
    ).fillna(0).round(1)

    delta["throughput_lift_pct"] = (
        (delta["after_points"] - delta["before_points"])
        / delta["before_points"].replace(0, np.nan) * 100
    ).fillna(0).round(1)

    return delta.sort_values("cycle_improvement_pct", ascending=False)


def resolution_heatmap_data(jira_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate cycle time by department × priority for heatmap.
    """
    if jira_df.empty:
        return pd.DataFrame()

    pivot = jira_df.pivot_table(
        values="cycle_time_hours",
        index="department",
        columns="priority",
        aggfunc="mean",
    ).fillna(0).round(2)

    return pivot.reset_index()
