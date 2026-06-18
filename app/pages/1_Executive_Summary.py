"""
app/pages/1_Executive_Summary.py
──────────────────────────────────
Standalone page: Executive Summary.
Accessible via Streamlit multi-page navigation sidebar.
Shows high-level KPIs, financial trends, and department benchmarks.
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import datetime

ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, CACHE_TTL
from src.data.loader import load_users, load_usage_logs, load_jira, load_github
from src.data.preprocessor import enrich_usage_logs, compute_user_summary, compute_dept_performance
from src.analysis.metrics import executive_kpis
from src.analysis.optimizer import classify_users, optimisation_summary
from src.analysis.correlation import benchmark_departments, monthly_trend_analysis
from app.components.charts import (
    dual_axis_trend, horizontal_bar, DARK, C
)

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

st.set_page_config(
    page_title="Executive Summary | AIFORGE",
    layout="wide", page_icon="📈"
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #0d1117; }
[data-testid="stSidebar"]          { background-color: #161b22 !important; }
*, p, label, div { color: #c9d1d9; }
h1, h2, h3       { color: #e6edf3 !important; }
.sec-hdr {
    font-size: 11px; font-weight: 600; color: #8b949e;
    text-transform: uppercase; letter-spacing: 1.2px;
    border-bottom: 1px solid #21262d; padding-bottom: 6px; margin: 16px 0 12px 0;
}
div[data-testid="stMetric"] { border-radius:12px; padding:18px 20px;
    border:1px solid #21262d; box-shadow:0 2px 8px rgba(0,0,0,0.4); }
div[data-testid="stMetricLabel"] > div { color:#8b949e !important; font-size:12px !important; }
div[data-testid="stMetricValue"] > div { color:#ffffff !important; font-size:26px !important; font-weight:700 !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _load():
    users   = load_users()
    logs    = load_usage_logs()
    jira    = load_jira()
    github  = load_github()
    enriched     = enrich_usage_logs(logs, users)
    user_summary = compute_user_summary(logs, jira, users, github)
    classified   = classify_users(user_summary)
    kpis         = executive_kpis(logs, jira, user_summary)
    monthly      = monthly_trend_analysis(logs, jira)
    bench        = benchmark_departments(classified)
    dept_perf    = compute_dept_performance(jira)
    return enriched, jira, classified, kpis, monthly, bench, dept_perf


if not DB_PATH.exists():
    st.error("Database not found. Run: `python scripts/setup_db.py`")
    st.stop()

logs, jira, classified, kpis, monthly, bench, dept_perf = _load()

# ── Header ───────────────────────────────────────────────
st.markdown("# 📈 Executive Summary")
st.caption(f"Global view · {len(logs):,} events · {logs['user_id'].nunique()} users · "
           f"{datetime.now().strftime('%d %b %Y %H:%M UTC')}")

# ── KPIs ─────────────────────────────────────────────────
opt = optimisation_summary(classified)
before_avg = jira[jira["period"]=="Before"]["cycle_time_hours"].mean() if not jira.empty else 0
after_avg  = jira[jira["period"]=="After" ]["cycle_time_hours"].mean() if not jira.empty else 0
pct_imp    = ((before_avg - after_avg) / before_avg * 100) if before_avg > 0 else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("💰 Total AI Spend",        f"${kpis['total_spend']:,.2f}")
k2.metric("⚡ Cycle Time Improvement", f"{pct_imp:.1f}%",     delta="Before → After")
k3.metric("🔑 Total Tokens",           f"{kpis['total_tokens']:,}")
k4.metric("🛡️ High/Critical Risk",    f"{kpis['high_risk_events']}")
k5.metric("💸 Monthly Savings Opp.",   f"${opt['total_monthly_saving']:,.2f}")

st.divider()

# ── Trend chart ──────────────────────────────────────────
st.markdown('<p class="sec-hdr">Daily Cost & Token Adoption</p>', unsafe_allow_html=True)

if "date" not in logs.columns:
    logs["date"] = pd.to_datetime(logs["timestamp"], errors="coerce").dt.date
trend = (
    logs.groupby("date")
    .agg(cost=("cost_usd","sum"), tokens=("token_count","sum"))
    .reset_index().sort_values("date")
)
fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Scatter(
    x=trend["date"], y=trend["tokens"], name="Tokens",
    line=dict(color="#58a6ff", width=2),
    fill="tozeroy", fillcolor="rgba(88,166,255,0.07)",
    hovertemplate="Tokens: %{y:,}<extra></extra>"
), secondary_y=False)
fig.add_trace(go.Bar(
    x=trend["date"], y=trend["cost"], name="Cost ($)",
    marker_color="rgba(240,136,62,0.55)",
    marker_line_color="#f0883e", marker_line_width=0.5,
    hovertemplate="Cost: $%{y:,.4f}<extra></extra>"
), secondary_y=True)
fig.update_layout(title="Daily Token Consumption vs Spend", height=340,
                  **{k:v for k,v in DARK.items() if k not in ("xaxis","yaxis")},
                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                  font=dict(color="#c9d1d9",size=12),
                  legend=dict(bgcolor="rgba(0,0,0,0)"),
                  hoverlabel=dict(bgcolor="#161b22",font_color="#e6edf3"),
                  margin=dict(l=0,r=0,t=36,b=0))
fig.update_yaxes(title_text="Tokens", secondary_y=False,
                 gridcolor="#21262d", tickcolor="#8b949e", tickfont=dict(size=10))
fig.update_yaxes(title_text="Cost ($)", secondary_y=True,
                 gridcolor="rgba(0,0,0,0)", tickcolor="#8b949e", tickfont=dict(size=10))
st.plotly_chart(fig, use_container_width=True)

# ── Dept spend + MoM ─────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    st.markdown('<p class="sec-hdr">Spend by Department</p>', unsafe_allow_html=True)
    dept_cost = logs.groupby("department")["cost_usd"].sum().sort_values().reset_index()
    fig2 = px.bar(
        dept_cost, x="cost_usd", y="department", orientation="h",
        color="cost_usd", color_continuous_scale=["#0d2137","#1f6feb","#58a6ff"],
        text="cost_usd",
        labels={"cost_usd":"Cost (USD)","department":""},
    )
    fig2.update_layout(height=300, showlegend=False, coloraxis_showscale=False,
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font=dict(color="#c9d1d9"), margin=dict(l=0,r=0,t=10,b=0))
    fig2.update_traces(texttemplate="$%{text:,.2f}", textposition="outside",
                       marker_line_width=0,
                       hovertemplate="%{y}: $%{x:,.2f}<extra></extra>")
    st.plotly_chart(fig2, use_container_width=True)

with col2:
    st.markdown('<p class="sec-hdr">Month-over-Month Spend</p>', unsafe_allow_html=True)
    if not monthly.empty:
        fig3 = px.bar(
            monthly, x="month_year", y="total_cost",
            color="total_cost", color_continuous_scale=["#0d2137","#58a6ff"],
            text="total_cost",
            labels={"month_year":"Month","total_cost":"Cost ($)"},
        )
        fig3.update_layout(height=300, showlegend=False, coloraxis_showscale=False,
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font=dict(color="#c9d1d9"), margin=dict(l=0,r=0,t=10,b=0))
        fig3.update_traces(texttemplate="$%{text:,.2f}", textposition="outside",
                           marker_line_width=0)
        st.plotly_chart(fig3, use_container_width=True)

# ── Department benchmark table ────────────────────────────
st.markdown('<p class="sec-hdr">Department Performance Benchmark</p>', unsafe_allow_html=True)
if not bench.empty:
    display = bench.copy()
    for c in ["total_spend","total_net_roi"]:
        if c in display.columns:
            display[c] = display[c].apply(lambda v: f"${v:,.2f}")
    if "avg_pct_improvement" in display.columns:
        display["avg_pct_improvement"] = display["avg_pct_improvement"].apply(lambda v: f"{v:.1f}%")
    if "zombie_pct" in display.columns:
        display["zombie_pct"] = display["zombie_pct"].apply(lambda v: f"{v:.1f}%")
    st.dataframe(display, use_container_width=True)
