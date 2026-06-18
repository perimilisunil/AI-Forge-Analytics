"""
app/pages/5_GitHub_Intelligence.py
────────────────────────────────────
Standalone GitHub Engineering Intelligence page.
Real data from 19 public repos · Before vs After Copilot (21 Jun 2022)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st

ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, CACHE_TTL, TARGET_REPOS, COPILOT_LAUNCH_DATE
from src.data.loader import load_users, load_github
from src.data.preprocessor import enrich_usage_logs
from src.github.pr_analyzer import (
    ensure_period_column, enrich_department,
    pr_performance_summary, compute_pr_efficiency_delta,
    top_contributors, repo_breakdown, velocity_trend_monthly,
)
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="GitHub Intelligence | AIFORGE",
    layout="wide", page_icon="🐙"
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #0d1117; }
[data-testid="stSidebar"]          { background-color: #161b22 !important; }
*, p, label, div { color: #c9d1d9; }
h1, h2, h3       { color: #e6edf3 !important; }
.sec-hdr {
    font-size:11px; font-weight:600; color:#8b949e;
    text-transform:uppercase; letter-spacing:1.2px;
    border-bottom:1px solid #21262d; padding-bottom:6px;
    margin:16px 0 12px 0;
}
.info-bar {
    background:#0d2137; border-left:3px solid #1f6feb;
    border-radius:4px; padding:9px 14px; margin:8px 0;
    color:#79c0ff; font-size:12px;
}
div[data-testid="stMetric"] {
    border-radius:12px; padding:18px; border:1px solid #21262d;
}
div[data-testid="stMetricLabel"] > div {
    color:#8b949e !important; font-size:12px !important;
}
div[data-testid="stMetricValue"] > div {
    color:#ffffff !important; font-size:24px !important;
    font-weight:700 !important;
}
</style>
""", unsafe_allow_html=True)

_D = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#c9d1d9", size=12),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    hoverlabel=dict(bgcolor="#161b22", font_color="#e6edf3"),
    margin=dict(l=0, r=0, t=36, b=0),
    xaxis=dict(gridcolor="#21262d", tickcolor="#8b949e", tickfont=dict(size=10)),
    yaxis=dict(gridcolor="#21262d", tickcolor="#8b949e", tickfont=dict(size=10)),
)
C = ["#58a6ff","#3fb950","#f0883e","#d2a8ff","#ffa657",
     "#ff7b72","#79c0ff","#56d364","#e3b341","#bc8cff"]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _load():
    github   = load_github()
    enriched = ensure_period_column(enrich_department(github))
    perf     = pr_performance_summary(enriched)
    delta    = compute_pr_efficiency_delta(perf)
    top      = top_contributors(enriched, n=20)
    repos    = repo_breakdown(enriched)
    monthly  = velocity_trend_monthly(enriched)
    return enriched, perf, delta, top, repos, monthly


if not DB_PATH.exists():
    st.error("Database not found. Run: `python scripts/setup_db.py`")
    st.stop()

gh, gh_perf, gh_delta, gh_top, gh_repos, gh_month = _load()

# ── Header ───────────────────────────────────────────────
st.markdown("# 🐙 GitHub Engineering Intelligence")
st.caption(
    f"Real PR data from **{len(TARGET_REPOS)} public repositories** · "
    f"Before/After boundary: **{COPILOT_LAUNCH_DATE.strftime('%d %b %Y')}** "
    f"(GitHub Copilot public launch)"
)

# ── Sidebar dept filter ───────────────────────────────────
with st.sidebar:
    dept_opts = ["All"] + sorted(gh["department"].dropna().unique().tolist()) if not gh.empty else ["All"]
    dept = st.selectbox("🏢 Department", dept_opts)
    period_f = st.selectbox("📅 Period", ["Both","Before","After"])

if dept != "All":
    gh       = gh      [gh      ["department"] == dept]
    gh_delta = gh_delta[gh_delta["department"] == dept] if "department" in gh_delta.columns else gh_delta
    gh_repos = gh_repos[gh_repos["department"] == dept]
    gh_month = gh_month[gh_month["department"] == dept]
    gh_top   = gh_top  [gh_top  ["department"] == dept]
    gh_perf  = gh_perf [gh_perf ["department"] == dept]

if period_f != "Both" and "period" in gh.columns:
    gh      = gh     [gh     ["period"] == period_f]
    gh_perf = gh_perf[gh_perf["period"] == period_f]

# ── KPIs ─────────────────────────────────────────────────
total_prs    = len(gh)
before_c     = gh[gh["period"]=="Before"]["cycle_time_hours"].mean() if "period" in gh.columns and not gh.empty else 0
after_c      = gh[gh["period"]=="After" ]["cycle_time_hours"].mean() if "period" in gh.columns and not gh.empty else 0
cyc_pct      = ((before_c - after_c) / before_c * 100) if before_c > 0 else 0
before_rw    = gh[gh["period"]=="Before"]["rework_ratio"].mean() if "period" in gh.columns and not gh.empty else 0
after_rw     = gh[gh["period"]=="After" ]["rework_ratio"].mean() if "period" in gh.columns and not gh.empty else 0
rw_pct       = ((before_rw - after_rw) / before_rw * 100) if before_rw > 0 else 0
contributors = gh["github_username"].nunique() if not gh.empty else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("🔀 Total PRs",             f"{total_prs:,}")
k2.metric("⚡ Cycle Time Improvement", f"{cyc_pct:.1f}%",
          delta=f"{before_c:.1f}h → {after_c:.1f}h")
k3.metric("♻️ Rework Ratio Drop",      f"{rw_pct:.1f}%",
          delta="Code quality signal")
k4.metric("👥 Contributors",           f"{contributors:,}")
k5.metric("📦 Repos",                  f"{gh['repo_name'].nunique() if not gh.empty else 0}")

st.markdown(f"""<div class="info-bar">
    📊 <b>Methodology:</b>
    PRs merged before <b>{COPILOT_LAUNCH_DATE.strftime('%d %b %Y')}</b> = Before AI era.
    PRs merged after = After AI era.
    Cycle time = merged_at − created_at (hours).
    Rework ratio = lines_removed / lines_added (lower = cleaner code).
    Data sourced from GitHub public REST API v3.
</div>""", unsafe_allow_html=True)

st.divider()

# ── Monthly trend ─────────────────────────────────────────
st.markdown('<p class="sec-hdr">Monthly PR Cycle Time Trend — Copilot Launch Marked</p>',
            unsafe_allow_html=True)
if not gh_month.empty:
    fig_t = px.line(
        gh_month, x="month", y="avg_cycle", color="department",
        color_discrete_sequence=C,
        labels={"month":"Month","avg_cycle":"Avg Merge Time (h)","department":"Dept"},
    )
    fig_t.add_vline(x="2022-06", line_dash="dash", line_color="#f0883e",
                    line_width=2, annotation_text="← Copilot Launch",
                    annotation_font_color="#f0883e", annotation_position="top right")
    fig_t.update_layout(title="Avg PR Merge Time by Department (Monthly)", height=320, **_D)
    fig_t.update_traces(line=dict(width=2),
                        hovertemplate="%{x}: %{y:.1f}h<extra>%{fullData.name}</extra>")
    st.plotly_chart(fig_t, use_container_width=True)

# ── Row 2 ─────────────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    st.markdown('<p class="sec-hdr">Cycle Time Improvement per Department</p>',
                unsafe_allow_html=True)
    if not gh_delta.empty and "pct_improvement" in gh_delta.columns:
        fig_i = px.bar(
            gh_delta.sort_values("pct_improvement"),
            x="pct_improvement", y="department", orientation="h",
            color="pct_improvement",
            color_continuous_scale=["#21262d","#3fb950"],
            text="pct_improvement",
            labels={"pct_improvement":"% Faster","department":""},
        )
        fig_i.update_layout(height=320, showlegend=False,
                            coloraxis_showscale=False, **_D)
        fig_i.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                            marker_line_width=0,
                            hovertemplate="%{y}: %{x:.1f}% faster<extra></extra>")
        st.plotly_chart(fig_i, use_container_width=True)

with c2:
    st.markdown('<p class="sec-hdr">Before vs After Avg Merge Time (hours)</p>',
                unsafe_allow_html=True)
    if not gh_delta.empty and "before_avg" in gh_delta.columns:
        melt = gh_delta.melt(
            id_vars=["department"],
            value_vars=["before_avg","after_avg"],
            var_name="period", value_name="avg_hours"
        )
        melt["period"] = melt["period"].map(
            {"before_avg":"Before Copilot","after_avg":"After Copilot"}
        )
        fig_ba = px.bar(
            melt, x="department", y="avg_hours", color="period",
            barmode="group",
            color_discrete_map={"Before Copilot":"#f0883e","After Copilot":"#3fb950"},
            text="avg_hours",
            labels={"avg_hours":"Hours","department":"","period":"Period"},
        )
        fig_ba.update_layout(height=320, **_D)
        fig_ba.update_traces(texttemplate="%{text:.1f}h", textposition="outside",
                             marker_line_width=0,
                             hovertemplate="%{x}: %{y:.1f}h<extra>%{fullData.name}</extra>")
        st.plotly_chart(fig_ba, use_container_width=True)

# ── Row 3 ─────────────────────────────────────────────────
c3, c4 = st.columns(2)
with c3:
    st.markdown('<p class="sec-hdr">Rework Ratio — Code Quality Before vs After</p>',
                unsafe_allow_html=True)
    if not gh_delta.empty and "before_rework" in gh_delta.columns:
        rw = gh_delta.melt(
            id_vars=["department"],
            value_vars=["before_rework","after_rework"],
            var_name="period", value_name="rework"
        )
        rw["period"] = rw["period"].map(
            {"before_rework":"Before Copilot","after_rework":"After Copilot"}
        )
        fig_rw = px.bar(
            rw, x="department", y="rework", color="period",
            barmode="group",
            color_discrete_map={"Before Copilot":"#f0883e","After Copilot":"#3fb950"},
            text="rework",
            labels={"rework":"Rework Ratio","department":"","period":"Period"},
        )
        fig_rw.update_layout(height=300, **_D)
        fig_rw.update_traces(texttemplate="%{text:.3f}", textposition="outside",
                             marker_line_width=0,
                             hovertemplate="%{x}: %{y:.3f}<extra>%{fullData.name}</extra>")
        st.plotly_chart(fig_rw, use_container_width=True)

with c4:
    st.markdown('<p class="sec-hdr">PR Volume by Repository</p>',
                unsafe_allow_html=True)
    if not gh_repos.empty:
        repo_vol = (
            gh_repos.groupby(["repo_name","department"])["pr_count"]
            .sum().reset_index().sort_values("pr_count")
        )
        fig_rv = px.bar(
            repo_vol, x="pr_count", y="repo_name",
            orientation="h", color="department",
            color_discrete_sequence=C,
            text="pr_count",
            labels={"pr_count":"PRs","repo_name":"","department":"Dept"},
        )
        fig_rv.update_layout(height=300, **_D)
        fig_rv.update_traces(texttemplate="%{text:,}", textposition="outside",
                             marker_line_width=0,
                             hovertemplate="%{y}: %{x:,} PRs<extra>%{fullData.name}</extra>")
        st.plotly_chart(fig_rv, use_container_width=True)

# ── Row 4 ─────────────────────────────────────────────────
with c5:
    st.markdown('<p class="sec-hdr">Monthly PR Throughput</p>',
                unsafe_allow_html=True)
    if not gh_month.empty:
        total_m = (
            gh_month.groupby("month")["pr_count"]
            .sum().reset_index().sort_values("month")
        )
        fig_th = px.area(
            total_m, x="month", y="pr_count",
            color_discrete_sequence=["#58a6ff"],
            labels={"month":"Month","pr_count":"PRs Merged"},
        )
        fig_th.add_vline(x="2022-06", line_dash="dash",
                         line_color="#f0883e", line_width=2,
                         annotation_text="Copilot →",
                         annotation_font_color="#f0883e",
                         annotation_position="top left")
        fig_th.update_layout(title="Total PRs Merged per Month", height=280, **_D)
        fig_th.update_traces(
            fillcolor="rgba(88,166,255,0.1)", line=dict(width=2),
            hovertemplate="%{x}: %{y:,} PRs<extra></extra>"
        )
        st.plotly_chart(fig_th, use_container_width=True)

# ── Tables ────────────────────────────────────────────────
st.markdown('<p class="sec-hdr">Top 20 Contributors — by PRs Merged</p>',
            unsafe_allow_html=True)
if not gh_top.empty:
    d = gh_top.copy()
    if "avg_cycle"   in d.columns: d["avg_cycle"]   = d["avg_cycle"].apply(lambda v: f"{v:.1f}h")
    if "avg_rework"  in d.columns: d["avg_rework"]  = d["avg_rework"].apply(lambda v: f"{v:.3f}")
    if "total_lines" in d.columns: d["total_lines"] = d["total_lines"].apply(lambda v: f"{int(v):,}")
    st.dataframe(d, use_container_width=True)

st.markdown('<p class="sec-hdr">Efficiency Delta Summary — All Departments</p>',
            unsafe_allow_html=True)
if not gh_delta.empty:
    st.dataframe(
        gh_delta.style.format({
            "before_avg":             "{:.1f}h",
            "after_avg":              "{:.1f}h",
            "hours_saved":            "{:.1f}h",
            "pct_improvement":        "{:.1f}%",
            "before_rework":          "{:.3f}",
            "after_rework":           "{:.3f}",
            "rework_improvement_pct": "{:.1f}%",
        }),
        use_container_width=True,
    )
