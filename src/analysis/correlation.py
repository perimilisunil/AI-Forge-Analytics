"""
src/analysis/correlation.py
────────────────────────────
Statistical correlation engine.
Computes:
  - Pearson & Spearman correlations between AI spend and productivity
  - OLS regression: cost → hours saved
  - Month-over-month trend analysis
  - Departmental efficiency benchmarking
"""

import numpy as np
import pandas as pd
from scipy import stats
from loguru import logger


def pearson_correlation(x: pd.Series, y: pd.Series) -> dict:
    """
    Compute Pearson r between two numeric series.
    Returns r, p-value, and interpretation.
    """
    clean = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(clean) < 3:
        return {"r": 0.0, "p_value": 1.0, "significant": False,
                "interpretation": "Insufficient data"}

    r, p = stats.pearsonr(clean["x"], clean["y"])
    return {
        "r":               round(float(r), 4),
        "p_value":         round(float(p), 4),
        "significant":     p < 0.05,
        "interpretation":  _interpret_r(r, p),
    }


def spearman_correlation(x: pd.Series, y: pd.Series) -> dict:
    """Spearman rank correlation — robust to outliers."""
    clean = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(clean) < 3:
        return {"rho": 0.0, "p_value": 1.0, "significant": False}

    rho, p = stats.spearmanr(clean["x"], clean["y"])
    return {
        "rho":         round(float(rho), 4),
        "p_value":     round(float(p), 4),
        "significant": p < 0.05,
    }


def ols_regression(x: pd.Series, y: pd.Series) -> dict:
    """
    Simple OLS: y = b0 + b1*x
    Returns slope, intercept, R², and predicted values.
    """
    clean = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(clean) < 3:
        return {"slope": 0.0, "intercept": 0.0, "r_squared": 0.0,
                "predicted": [], "n": 0}

    slope, intercept, r, p, se = stats.linregress(clean["x"], clean["y"])
    predicted = slope * clean["x"] + intercept

    return {
        "slope":      round(float(slope), 6),
        "intercept":  round(float(intercept), 4),
        "r_squared":  round(float(r ** 2), 4),
        "p_value":    round(float(p), 4),
        "std_err":    round(float(se), 6),
        "predicted":  predicted.tolist(),
        "x_values":   clean["x"].tolist(),
        "y_values":   clean["y"].tolist(),
        "n":          len(clean),
    }


def spend_vs_productivity_analysis(user_summary: pd.DataFrame) -> dict:
    """
    Full correlation analysis: AI spend vs productivity metrics.
    Returns a dict of results for each relationship tested.
    """
    results = {}

    if user_summary.empty:
        return results

    required = ["total_cost", "hours_saved_per_ticket",
                "pct_improvement", "tickets_closed", "net_roi"]
    for col in required:
        if col not in user_summary.columns:
            user_summary[col] = 0.0

    # 1. Spend → Hours Saved
    results["cost_vs_hours_saved"] = {
        "pearson":  pearson_correlation(user_summary["total_cost"],
                                        user_summary["hours_saved_per_ticket"]),
        "spearman": spearman_correlation(user_summary["total_cost"],
                                         user_summary["hours_saved_per_ticket"]),
        "ols":      ols_regression(user_summary["total_cost"],
                                   user_summary["hours_saved_per_ticket"]),
        "label":    "AI Spend ($) vs Hours Saved per Ticket",
    }

    # 2. Spend → Efficiency %
    results["cost_vs_efficiency"] = {
        "pearson":  pearson_correlation(user_summary["total_cost"],
                                        user_summary["pct_improvement"]),
        "ols":      ols_regression(user_summary["total_cost"],
                                   user_summary["pct_improvement"]),
        "label":    "AI Spend ($) vs Efficiency Improvement (%)",
    }

    # 3. Spend → Tickets Closed
    results["cost_vs_tickets"] = {
        "pearson":  pearson_correlation(user_summary["total_cost"],
                                        user_summary["tickets_closed"]),
        "ols":      ols_regression(user_summary["total_cost"],
                                   user_summary["tickets_closed"]),
        "label":    "AI Spend ($) vs Tickets Closed",
    }

    # 4. Spend → Net ROI
    results["cost_vs_roi"] = {
        "pearson":  pearson_correlation(user_summary["total_cost"],
                                        user_summary["net_roi"]),
        "ols":      ols_regression(user_summary["total_cost"],
                                   user_summary["net_roi"]),
        "label":    "AI Spend ($) vs Net ROI ($)",
    }

    logger.info("Correlation analysis complete — "
                f"{len(results)} relationships analysed")
    return results


def monthly_trend_analysis(logs: pd.DataFrame,
                            jira: pd.DataFrame) -> pd.DataFrame:
    """
    Month-over-month trend: cost, tokens, efficiency improvement.
    Returns a DataFrame indexed by month_year.
    """
    if logs.empty:
        return pd.DataFrame()

    logs = logs.copy()
    if "month_year" not in logs.columns:
        logs["month_year"] = pd.to_datetime(
            logs["timestamp"], errors="coerce"
        ).dt.to_period("M").astype(str)

    monthly_cost = (
        logs.groupby("month_year")
        .agg(total_cost=("cost_usd", "sum"),
             total_tokens=("token_count", "sum"),
             active_users=("user_id", "nunique"),
             prompt_count=("prompt_id", "count"))
        .reset_index()
        .sort_values("month_year")
    )

    # MoM % change
    monthly_cost["cost_mom_pct"] = (
        monthly_cost["total_cost"].pct_change() * 100
    ).round(1)

    return monthly_cost


def benchmark_departments(user_summary: pd.DataFrame) -> pd.DataFrame:
    """
    Rank departments by efficiency gain and ROI.
    Returns sorted DataFrame for competitive comparison.
    """
    if user_summary.empty or "department" not in user_summary.columns:
        return pd.DataFrame()

    dept = (
        user_summary.groupby("department")
        .agg(
            headcount=("user_id", "count"),
            total_spend=("total_cost", "sum"),
            avg_pct_improvement=("pct_improvement", "mean"),
            total_net_roi=("net_roi", "sum"),
            avg_hours_saved=("hours_saved_per_ticket", "mean"),
            total_tickets=("tickets_closed", "sum"),
            zombie_count=("is_zombie", "sum"),
        )
        .reset_index()
    )

    dept["roi_per_dollar_spent"] = (
        dept["total_net_roi"] / dept["total_spend"].replace(0, np.nan)
    ).fillna(0).round(3)

    dept["zombie_pct"] = (
        dept["zombie_count"] / dept["headcount"] * 100
    ).round(1)

    return dept.sort_values("avg_pct_improvement", ascending=False)


def _interpret_r(r: float, p: float) -> str:
    if p >= 0.05:
        return "Not statistically significant"
    if abs(r) >= 0.7:
        strength = "Strong"
    elif abs(r) >= 0.4:
        strength = "Moderate"
    else:
        strength = "Weak"
    direction = "positive" if r > 0 else "negative"
    return f"{strength} {direction} correlation (r={r:.2f}, p={p:.3f})"
