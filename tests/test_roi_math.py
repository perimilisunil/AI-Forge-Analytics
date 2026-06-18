"""
tests/test_roi_math.py
───────────────────────
Unit tests for ROI calculation, optimisation, and correlation math.
Run: pytest tests/test_roi_math.py -v
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.metrics import (
    calculate_user_roi, calculate_dept_risk_score, risk_score_to_level
)
from src.analysis.optimizer import (
    classify_users, optimisation_summary, LICENCE_COSTS
)
from src.analysis.correlation import (
    pearson_correlation, spearman_correlation, ols_regression
)


# ═══════════════════════════════════════════════════════
# ROI CALCULATIONS
# ═══════════════════════════════════════════════════════

class TestROICalculation:

    def test_positive_roi_basic(self):
        """User saves more than they cost → positive ROI."""
        result = calculate_user_roi(
            avg_cycle_before=48.0,
            avg_cycle_after=30.0,
            tickets_closed=20,
            hourly_rate=50.0,
            total_ai_cost=500.0,
        )
        # hours_saved = 18h, dollar_saved = 18*20*50 = 18000
        assert result["hours_saved_per_ticket"] == 18.0
        assert result["dollar_value_saved"] == 18_000.0
        assert result["net_roi"] == 17_500.0
        assert result["roi_positive"] is True

    def test_negative_roi_when_cost_exceeds_savings(self):
        """Very small savings + large AI cost → negative ROI."""
        result = calculate_user_roi(
            avg_cycle_before=10.0,
            avg_cycle_after=9.5,
            tickets_closed=1,
            hourly_rate=20.0,
            total_ai_cost=1_000.0,
        )
        assert result["net_roi"] < 0
        assert result["roi_positive"] is False

    def test_zero_before_cycle_time(self):
        """Handles division by zero — pct_improvement should be 0."""
        result = calculate_user_roi(
            avg_cycle_before=0.0,
            avg_cycle_after=0.0,
            tickets_closed=10,
            hourly_rate=50.0,
            total_ai_cost=100.0,
        )
        assert result["pct_improvement"] == 0.0
        assert result["hours_saved_per_ticket"] == 0.0

    def test_hours_saved_never_negative(self):
        """After > Before (regression) — hours_saved clipped to 0."""
        result = calculate_user_roi(
            avg_cycle_before=20.0,
            avg_cycle_after=30.0,   # worse after AI!
            tickets_closed=10,
            hourly_rate=50.0,
            total_ai_cost=100.0,
        )
        assert result["hours_saved_per_ticket"] == 0.0
        assert result["dollar_value_saved"] == 0.0

    def test_pct_improvement_correct(self):
        """48h before, 30h after → 37.5% improvement."""
        result = calculate_user_roi(48, 30, 10, 50, 100)
        assert abs(result["pct_improvement"] - 37.5) < 0.1

    def test_zero_tickets_closed(self):
        """No tickets = no dollar value saved (zombie scenario)."""
        result = calculate_user_roi(48, 20, 0, 50, 500)
        assert result["dollar_value_saved"] == 0.0
        assert result["net_roi"] == -500.0


# ═══════════════════════════════════════════════════════
# RISK SCORING
# ═══════════════════════════════════════════════════════

class TestRiskScoring:

    def test_risk_level_thresholds(self):
        assert risk_score_to_level(0)   == "Low"
        assert risk_score_to_level(25)  == "Medium"
        assert risk_score_to_level(50)  == "High"
        assert risk_score_to_level(75)  == "Critical"
        assert risk_score_to_level(99)  == "Critical"

    def test_dept_risk_empty_series(self):
        assert calculate_dept_risk_score(pd.Series([], dtype=float)) == 0.0

    def test_dept_risk_all_zeros(self):
        assert calculate_dept_risk_score(pd.Series([0, 0, 0])) == 0.0

    def test_dept_risk_normal_values(self):
        scores = pd.Series([10, 30, 50, 70, 80, 90])
        result = calculate_dept_risk_score(scores)
        assert 0 < result <= 100

    def test_dept_risk_capped_at_100(self):
        scores = pd.Series([100, 100, 100, 100])
        assert calculate_dept_risk_score(scores) <= 100.0


# ═══════════════════════════════════════════════════════
# ZOMBIE DETECTION & OPTIMISATION
# ═══════════════════════════════════════════════════════

class TestZombieDetection:

    def _make_summary(self) -> pd.DataFrame:
        """Build a minimal user_summary DataFrame for testing."""
        return pd.DataFrame([
            {
                "user_id": "U001", "employee_name": "Alice", "department": "Engineering",
                "role": "Senior Engineer", "license_type": "Enterprise",
                "hourly_rate": 80.0, "github_username": "alice_gh",
                "total_cost": 500.0, "total_tokens": 100_000, "prompt_count": 200,
                "avg_cycle_before": 48.0, "avg_cycle_after": 30.0,
                "tickets_closed": 20, "prs_merged": 5,
                "hours_saved_per_ticket": 18.0, "dollar_value_saved": 28_800.0,
                "net_roi": 28_300.0, "pct_improvement": 37.5, "is_zombie": 0,
            },
            {
                "user_id": "U002", "employee_name": "Bob", "department": "Sales",
                "role": "AE", "license_type": "Enterprise",
                "hourly_rate": 50.0, "github_username": None,
                "total_cost": 900.0, "total_tokens": 200_000, "prompt_count": 400,
                "avg_cycle_before": 24.0, "avg_cycle_after": 24.0,
                "tickets_closed": 0, "prs_merged": 0,
                "hours_saved_per_ticket": 0.0, "dollar_value_saved": 0.0,
                "net_roi": -900.0, "pct_improvement": 0.0, "is_zombie": 1,
            },
            {
                "user_id": "U003", "employee_name": "Carol", "department": "Engineering",
                "role": "Staff Engineer", "license_type": "Pro",
                "hourly_rate": 90.0, "github_username": "carol_gh",
                "total_cost": 50.0, "total_tokens": 5_000, "prompt_count": 8,
                "avg_cycle_before": 40.0, "avg_cycle_after": 35.0,
                "tickets_closed": 3, "prs_merged": 2,
                "hours_saved_per_ticket": 5.0, "dollar_value_saved": 1_350.0,
                "net_roi": 1_300.0, "pct_improvement": 12.5, "is_zombie": 0,
            },
        ])

    def test_zombie_identified(self):
        classified = classify_users(self._make_summary())
        zombie_ids = classified[classified["is_zombie"] == 1]["user_id"].tolist()
        assert "U002" in zombie_ids

    def test_active_user_not_zombie(self):
        classified = classify_users(self._make_summary())
        assert classified[classified["user_id"] == "U001"]["is_zombie"].values[0] == 0

    def test_optimisation_summary_keys(self):
        classified = classify_users(self._make_summary())
        opt = optimisation_summary(classified)
        for key in ["zombie_count", "total_monthly_saving",
                    "annual_saving_projection", "zombie_pct"]:
            assert key in opt

    def test_monthly_saving_non_negative(self):
        classified = classify_users(self._make_summary())
        opt = optimisation_summary(classified)
        assert opt["total_monthly_saving"] >= 0

    def test_annual_projection_is_12x_monthly(self):
        classified = classify_users(self._make_summary())
        opt = optimisation_summary(classified)
        assert abs(opt["annual_saving_projection"] - opt["total_monthly_saving"] * 12) < 0.01


# ═══════════════════════════════════════════════════════
# STATISTICAL CORRELATION
# ═══════════════════════════════════════════════════════

class TestCorrelation:

    def test_pearson_perfect_positive(self):
        x = pd.Series([1, 2, 3, 4, 5])
        y = pd.Series([2, 4, 6, 8, 10])
        r = pearson_correlation(x, y)
        assert abs(r["r"] - 1.0) < 1e-6
        assert r["significant"] is True

    def test_pearson_no_correlation(self):
        rng = np.random.default_rng(42)
        x = pd.Series(rng.uniform(0, 100, 200))
        y = pd.Series(rng.uniform(0, 100, 200))
        r = pearson_correlation(x, y)
        assert abs(r["r"]) < 0.25   # near zero

    def test_pearson_insufficient_data(self):
        r = pearson_correlation(pd.Series([1, 2]), pd.Series([1, 2]))
        assert r["significant"] is False

    def test_ols_slope_and_intercept(self):
        x = pd.Series([0, 1, 2, 3, 4])
        y = pd.Series([1, 3, 5, 7, 9])   # y = 2x + 1
        result = ols_regression(x, y)
        assert abs(result["slope"]     - 2.0) < 0.01
        assert abs(result["intercept"] - 1.0) < 0.01
        assert abs(result["r_squared"] - 1.0) < 1e-6

    def test_ols_r_squared_range(self):
        rng = np.random.default_rng(0)
        x = pd.Series(rng.uniform(0, 100, 50))
        y = x * 0.5 + rng.normal(0, 5, 50)
        result = ols_regression(pd.Series(x), pd.Series(y))
        assert 0 <= result["r_squared"] <= 1

    def test_spearman_monotonic(self):
        x = pd.Series([1, 2, 3, 4, 5])
        y = pd.Series([1, 4, 9, 16, 25])   # monotonic but nonlinear
        r = spearman_correlation(x, y)
        assert abs(r["rho"] - 1.0) < 1e-6
