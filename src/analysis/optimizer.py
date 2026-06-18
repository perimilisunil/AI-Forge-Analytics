"""
src/analysis/optimizer.py
──────────────────────────
Licence Intelligence Engine.
Classifies every user into one of 5 categories based on
AI spend vs measurable productivity output:

    Champion       → High spend + High ROI    (reward)
    Healthy        → Normal usage + output     (maintain)
    Underutilized  → Low spend + low output    (coach)
    At-Risk        → High spend + low output   (investigate)
    Zombie         → High spend + zero output  (revoke licence)

This replaces the old binary is_zombie flag with a
richer AI Workforce Optimisation model.
"""

import numpy as np
import pandas as pd
from loguru import logger


# ─── Licence tier monthly costs (USD) ────────────────────
LICENCE_COSTS: dict[str, float] = {
    "Enterprise": 30.00,
    "Pro":        20.00,
    "Free":        0.00,
}

LICENCE_THRESHOLDS: dict[str, dict] = {
    "Enterprise": {"min_tokens": 50_000,  "min_prompts": 50,  "min_tickets": 5},
    "Pro":        {"min_tokens": 10_000,  "min_prompts": 10,  "min_tickets": 1},
    "Free":       {"min_tokens": 0,       "min_prompts": 0,   "min_tickets": 0},
}

# ─── Category thresholds ─────────────────────────────────
# All percentile-based so they adapt to any dataset size
CHAMPION_PCT_THRESHOLD    = 70   # pct_improvement ≥ 70th percentile → Champion
AT_RISK_COST_PCT          = 60   # total_cost ≥ 60th percentile
AT_RISK_OUTPUT_PCT        = 30   # tickets_closed ≤ 30th percentile
UNDERUTIL_COST_PCT        = 40   # total_cost ≤ 40th percentile
UNDERUTIL_OUTPUT_PCT      = 40   # tickets_closed ≤ 40th percentile


# ─────────────────────────────────────────────────────────
# CATEGORY CLASSIFICATION
# ─────────────────────────────────────────────────────────

def classify_users(user_summary: pd.DataFrame) -> pd.DataFrame:
    """
    Classify every user into one of 5 categories and add:
      - category          : string label
      - category_emoji    : visual label
      - recommended_tier  : suggested licence tier
      - potential_saving  : monthly saving if recommendation applied
      - is_zombie         : kept for backward compatibility (0/1)
    """
    df = user_summary.copy()

    # Ensure required columns exist
    for col in ["total_cost", "total_tokens", "prompt_count",
                "tickets_closed", "prs_merged", "license_type",
                "pct_improvement", "net_roi"]:
        if col not in df.columns:
            df[col] = 0.0

    n = len(df)
    if n == 0:
        return df

    # ── Compute percentile thresholds ────────────────────
    cost_p60    = df["total_cost"].quantile(0.60)
    cost_p40    = df["total_cost"].quantile(0.40)
    output_p30  = df["tickets_closed"].quantile(0.30)
    output_p40  = df["tickets_closed"].quantile(0.40)
    impr_p70    = df["pct_improvement"].quantile(0.70)
    median_cost = df["total_cost"].median()

    # ── Assign categories ─────────────────────────────────
    def _categorise(row) -> tuple:
        cost    = row["total_cost"]
        tickets = row["tickets_closed"]
        impr    = row["pct_improvement"]
        roi     = row["net_roi"]

        # Zombie: high cost AND zero measurable output
        if cost > cost_p60 and tickets == 0:
            return ("Zombie",        "🧟 Zombie")

        # At-Risk: high cost AND low (but non-zero) output
        if cost >= cost_p60 and tickets <= output_p30 and tickets > 0:
            return ("At-Risk",       "⚠️ At-Risk")

        # Champion: high improvement percentile AND positive ROI
        if impr >= impr_p70 and roi > 0:
            return ("Champion",      "⭐ Champion")

        # Underutilized: low cost AND low output
        if cost <= cost_p40 and tickets <= output_p40:
            return ("Underutilized", "💤 Underutilized")

        # Everything else: healthy productive user
        return ("Healthy", "✅ Healthy")

    categories = df.apply(_categorise, axis=1)
    df["category"]       = categories.apply(lambda x: x[0])
    df["category_emoji"] = categories.apply(lambda x: x[1])

    # ── Backward-compatible is_zombie flag ───────────────
    df["is_zombie"] = (df["category"] == "Zombie").astype(int)

    # ── Recommended licence tier ─────────────────────────
    df["recommended_tier"] = df.apply(_recommend_tier, axis=1)

    df["current_licence_cost"] = (
        df.get("license_type", pd.Series("Pro", index=df.index))
        .map(LICENCE_COSTS).fillna(0)
    )
    df["recommended_licence_cost"] = df["recommended_tier"].map(LICENCE_COSTS).fillna(0)
    df["potential_saving"] = (
        df["current_licence_cost"] - df["recommended_licence_cost"]
    ).clip(lower=0)

    # ── Log category distribution ─────────────────────────
    dist = df["category"].value_counts().to_dict()
    logger.info(
        f"User classification complete — "
        + " | ".join(f"{k}: {v}" for k, v in dist.items())
    )
    return df


def _recommend_tier(row) -> str:
    tokens  = row.get("total_tokens",  0)
    prompts = row.get("prompt_count",  0)
    tickets = row.get("tickets_closed", 0)
    for tier in ["Enterprise", "Pro", "Free"]:
        t = LICENCE_THRESHOLDS[tier]
        if (tokens  >= t["min_tokens"] or
            prompts >= t["min_prompts"] or
            tickets >= t["min_tickets"]):
            return tier
    return "Free"


# ─────────────────────────────────────────────────────────
# SUMMARY & REPORTING
# ─────────────────────────────────────────────────────────

def optimisation_summary(classified: pd.DataFrame) -> dict:
    """High-level optimisation summary for KPI strip."""
    total = len(classified)
    if total == 0:
        return {k: 0 for k in [
            "total_users","champion_count","healthy_count","underutil_count",
            "at_risk_count","zombie_count","zombie_pct","downgrade_candidates",
            "monthly_saving_zombies","monthly_saving_downgrades",
            "total_monthly_saving","annual_saving_projection"
        ]}

    cats = classified["category"].value_counts().to_dict()

    zombies    = classified[classified["category"] == "Zombie"]
    at_risk    = classified[classified["category"] == "At-Risk"]
    downgrade  = classified[
        (classified["category"].isin(["Zombie","At-Risk","Underutilized"])) &
        (classified["potential_saving"] > 0)
    ]

    monthly_z  = zombies["current_licence_cost"].sum()
    monthly_d  = downgrade["potential_saving"].sum()
    total_save = monthly_z + monthly_d

    return {
        "total_users":               total,
        "champion_count":            cats.get("Champion",      0),
        "healthy_count":             cats.get("Healthy",       0),
        "underutil_count":           cats.get("Underutilized", 0),
        "at_risk_count":             cats.get("At-Risk",       0),
        "zombie_count":              cats.get("Zombie",        0),
        "zombie_pct":                round(cats.get("Zombie", 0) / total * 100, 1),
        "downgrade_candidates":      len(downgrade),
        "monthly_saving_zombies":    round(monthly_z,  2),
        "monthly_saving_downgrades": round(monthly_d,  2),
        "total_monthly_saving":      round(total_save, 2),
        "annual_saving_projection":  round(total_save * 12, 2),
    }


def category_distribution(classified: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a DataFrame with category counts and percentages —
    ready for a bar/donut chart.
    """
    ORDER  = ["Champion", "Healthy", "Underutilized", "At-Risk", "Zombie"]
    COLORS = {
        "Champion":      "#3fb950",
        "Healthy":       "#58a6ff",
        "Underutilized": "#e3b341",
        "At-Risk":       "#f0883e",
        "Zombie":        "#ff7b72",
    }
    EMOJI = {
        "Champion":      "⭐",
        "Healthy":       "✅",
        "Underutilized": "💤",
        "At-Risk":       "⚠️",
        "Zombie":        "🧟",
    }

    counts = classified["category"].value_counts()
    total  = max(len(classified), 1)

    rows = []
    for cat in ORDER:
        n = counts.get(cat, 0)
        rows.append({
            "category":   cat,
            "emoji":      EMOJI[cat],
            "count":      n,
            "pct":        round(n / total * 100, 1),
            "color":      COLORS[cat],
        })
    return pd.DataFrame(rows)


def top_performers_table(user_summary: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top N users ranked by pct_improvement (Champions and Healthy)."""
    cols = [c for c in [
        "user_id", "employee_name", "department", "role",
        "category", "pct_improvement", "tickets_closed",
        "hours_saved_per_ticket", "net_roi", "total_cost"
    ] if c in user_summary.columns]
    return (
        user_summary[cols]
        .nlargest(n, "pct_improvement")
        .reset_index(drop=True)
    )


def zombies_table(classified: pd.DataFrame) -> pd.DataFrame:
    """All zombie users sorted by wasted spend."""
    zombies = classified[classified["category"] == "Zombie"].copy()
    cols = [c for c in [
        "user_id", "employee_name", "department", "role",
        "license_type", "total_cost", "total_tokens",
        "prompt_count", "tickets_closed",
        "current_licence_cost", "category_emoji"
    ] if c in zombies.columns]
    return zombies[cols].sort_values("total_cost", ascending=False).reset_index(drop=True)


def at_risk_table(classified: pd.DataFrame) -> pd.DataFrame:
    """At-Risk users — high spend, low output."""
    at_risk = classified[classified["category"] == "At-Risk"].copy()
    cols = [c for c in [
        "user_id", "employee_name", "department", "role",
        "total_cost", "tickets_closed", "pct_improvement",
        "net_roi", "recommended_tier", "potential_saving"
    ] if c in at_risk.columns]
    return at_risk[cols].sort_values("total_cost", ascending=False).reset_index(drop=True)
