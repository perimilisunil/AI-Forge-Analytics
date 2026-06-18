"""
app/pages/2_Productivity_Insights.py
──────────────────────────────────────
Standalone page: Productivity & ROI deep-dive.
Before/After Jira cycle time, story point velocity, regression analysis.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st

ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, CACHE_TTL
from src.data.loader import load_users, load_usage_logs, load_jira, load_github
from src.data.preprocessor import enrich_usage_logs, compute_user_summary, compute_dept_performance
from src.analysis.optimizer import classify_users
from src.analysis.correlation import spend_vs_productivity_analysis
from src.jira.ticket_analyzer import velocity_analysis, compute_throughput_delta, priority_breakdown
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Productivity | AIFORGE", layout="wide", page_icon="🚀")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #0d1117; }
[data-testid="stSidebar"]          { background-color: #161b22 !important; }
*, p, label, div { color: #c9d1d9; }
h1, h2, h3       { color: #e6edf3 !important; }
.sec-hdr { font-size:11px; font-weight:600; color:#8b949e; text-transform:uppercase;
    letter-spacing:1.2px; border-bottom:1px solid #21262d; padding-bottom:6px; margin:16px 0 12px 0; }
div[data-testid="stMetric"] { border-radius:12px; padding:18px; border:1px solid #21262d; }
div[data-testid="stMetricLabel"] > div { color:#8b949e !important; font-size:12px !important; }
div[data-testid="stMetricValue"] > div { color:#ffffff !important; font-size:24px !important; font-weight:700 !important; }
</style>
""", unsafe_allow_html=True)

_DARK = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             font=dict(color="#c9d1d9", size=12),
             legend=dict(bgcolor="rgba(0,0,0,0)"),
             hoverlabel=dict(bgcolor="#161b22", font_color="#e6edf3"),
             margin=dict(l=0, r=0, t=36, b=0))


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _load():
    users        = load_users()
    logs         = load_usage_logs()
    jira         = load_jira()
    github       = load_github()
    enriched     = enrich_usage_logs(logs, users)
    user_summary = compute_user_summary(logs, jira, users, github)
    classified   = classify_users(user_summary)
    dept_perf    = compute_dept_performance(jira)
    velocity     = velocity_analysis(jira)
    thruput      = compute_throughput_delta(velocity)
    corr         = spend_vs_productivity_analysis(classified)
    return jira, enriched, classified, dept_perf, velocity, thruput, corr


if not DB_PATH.exists():
    st.error("Database not found. Run: `python scripts/setup_db.py`")
    st.stop()

jira, logs, classified, dept_perf, velocity, thruput, corr = _load()

st.markdown("# 🚀 Productivity & ROI Impact")

# ── Top KPIs ─────────────────────────────────────────────
before_avg = jira[jira["period"]=="Before"]["cycle_time_hours"].mean() if not jira.empty else 0
after_avg  = jira[jira["period"]=="After" ]["cycle_time_hours"].mean() if not jira.empty else 0
pct_imp    = ((before_avg - after_avg) / before_avg * 100) if before_avg > 0 else 0
hrs_saved  = before_avg - after_avg if before_avg > after_avg else 0
total_roi  = classified["net_roi"].sum() if "net_roi" in classified.columns else 0
top_dept   = dept_perf.nlargest(1,"pct_improvement")["department"].values[0] \
             if not dept_perf.empty and "pct_improvement" in dept_perf.columns else "—"

k1, k2, k3, k4 = st.columns(4)
k1.metric("⚡ Overall Efficiency Gain", f"{pct_imp:.1f}%",      delta="Cycle time improvement")
k2.metric("⏱️ Avg Hours Saved/Ticket",  f"{hrs_saved:.1f}h",    delta="Before − After")
k3.metric("💰 Total Net ROI",           f"${total_roi:,.0f}",    delta="Dollar value saved − AI cost")
k4.metric("🏆 Top Department",          top_dept,                delta="Highest efficiency gain")

st.divider()

# ── Before / After grouped bar ───────────────────────────
st.markdown('<p class="sec-hdr">Cycle Time: Before vs After AI Adoption</p>', unsafe_allow_html=True)
col1, col2 = st.columns(2)

with col1:
    ba_agg = (
        jira.groupby(["department","period"])["cycle_time_hours"]
        .mean().reset_index()
    )
    ba_agg.columns = ["department","period","mean_hours"]
    ba_agg["mean_hours"] = ba_agg["mean_hours"].round(1)
    fig = px.bar(
        ba_agg, x="department", y="mean_hours", color="period",
        barmode="group", title="Avg Cycle Time per Department (hours)",
        color_discrete_map={"Before":"#f0883e","After":"#3fb950"},
        text="mean_hours",
        labels={"mean_hours":"Avg Hours","department":"","period":"Period"},
    )
    fig.update_layout(height=360, **_DARK)
    fig.update_traces(texttemplate="%{text:.1f}h", textposition="outside",
                      marker_line_width=0,
                      hovertemplate="%{x} | %{fullData.name}: %{y:.1f} hrs<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    if not dept_perf.empty and "pct_improvement" in dept_perf.columns:
        fig2 = px.bar(
            dept_perf.sort_values("pct_improvement"),
            x="pct_improvement", y="department", orientation="h",
            title="Efficiency Gain by Department (%)",
            color="pct_improvement",
            color_continuous_scale=["#21262d","#3fb950"],
            text="pct_improvement",
            labels={"pct_improvement":"% Improvement","department":""},
        )
        fig2.update_layout(height=360, showlegend=False,
                           coloraxis_showscale=False, **_DARK)
        fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                           marker_line_width=0,
                           hovertemplate="%{y}: %{x:.1f}% improvement<extra></extra>")
        st.plotly_chart(fig2, use_container_width=True)

# ── Story points vs cycle time regression ────────────────
st.markdown('<p class="sec-hdr">Story Points vs Cycle Time — OLS Regression</p>', unsafe_allow_html=True)
col3, col4 = st.columns(2)

with col3:
    sc = jira[(jira["story_points"] > 0) & (jira["cycle_time_hours"] > 0)]
    if len(sc) > 5:
        fig3 = px.scatter(
            sc, x="story_points", y="cycle_time_hours",
            color="period", trendline="ols",
            title="Story Points vs Cycle Time (Before & After)",
            color_discrete_map={"Before":"#f0883e","After":"#3fb950"},
            labels={"story_points":"Story Points",
                    "cycle_time_hours":"Cycle Time (h)",
                    "period":"Period"},
        )
        fig3.update_layout(height=340, **_DARK)
        fig3.update_traces(
            hovertemplate="%{x} pts → %{y:.1f}h<extra>%{fullData.name}</extra>"
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Not enough data for regression (need > 5 data points).")

with col4:
    pri_agg = (
        jira.groupby(["priority","period"])["jira_issue_id"]
        .count().reset_index()
    )
    pri_agg.columns = ["priority","period","count"]
    fig4 = px.bar(
        pri_agg, x="priority", y="count", color="period",
        barmode="group", title="Ticket Count by Priority",
        color_discrete_map={"Before":"#f0883e","After":"#3fb950"},
        labels={"priority":"Priority","count":"Tickets","period":"Period"},
        category_orders={"priority":["Low","Medium","High","Critical"]},
    )
    fig4.update_layout(height=340, **_DARK)
    fig4.update_traces(marker_line_width=0,
                       hovertemplate="%{x} | %{fullData.name}: %{y}<extra></extra>")
    st.plotly_chart(fig4, use_container_width=True)

# ── Throughput delta + Correlation tables ─────────────────
st.markdown('<p class="sec-hdr">Throughput Delta & Correlation Analysis</p>', unsafe_allow_html=True)
col5, col6 = st.columns(2)

with col5:
    if not thruput.empty:
        st.dataframe(
            thruput.style.format({
                "before_cycle":           "{:.1f}h",
                "after_cycle":            "{:.1f}h",
                "hours_saved":            "{:.1f}h",
                "cycle_improvement_pct":  "{:.1f}%",
                "throughput_lift_pct":    "{:.1f}%",
            }),
            use_container_width=True, height=300
        )

with col6:
    # Summarise correlations into a clean table
    rows = []
    for key, res in corr.items():
        p = res.get("pearson", {})
        rows.append({
            "Relationship":    res.get("label", key),
            "Pearson r":       p.get("r", 0),
            "p-value":         p.get("p_value", 1),
            "Significant":     "✅ Yes" if p.get("significant") else "❌ No",
            "Interpretation":  p.get("interpretation","—"),
        })
    if rows:
        corr_df = pd.DataFrame(rows)
        st.dataframe(
            corr_df.style.format({
                "Pearson r": "{:.4f}",
                "p-value":   "{:.4f}",
            }),
            use_container_width=True, height=300
        )
