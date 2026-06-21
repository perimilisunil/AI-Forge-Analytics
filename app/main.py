import sys
from pathlib import Path
from narwhals import col
import numpy as np
import pandas as pd
import plotly.express as pxIST
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, CACHE_TTL, TARGET_REPOS, COPILOT_LAUNCH_DATE, DEPARTMENTS
from src.data.loader import load_users, load_usage_logs, load_jira, load_github
from src.data.preprocessor import (
    enrich_usage_logs, compute_dept_performance, compute_user_summary
)
from src.analysis.metrics import executive_kpis
from src.analysis.optimizer import classify_users, optimisation_summary, top_performers_table, zombies_table, category_distribution, at_risk_table
from src.analysis.correlation import (
    spend_vs_productivity_analysis, monthly_trend_analysis, benchmark_departments
)
from src.jira.ticket_analyzer import velocity_analysis, priority_breakdown, compute_throughput_delta
from src.github.pr_analyzer import (
    ensure_period_column, enrich_department,
    pr_performance_summary, compute_pr_efficiency_delta,
    top_contributors, repo_breakdown, velocity_trend_monthly,
)

# ═══════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AIFORGE | Enterprise AI Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🔷",
)

# ═══════════════════════════════════════════════════════════
# GLOBAL CSS
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>

/* ═══════════════════════════════════════════════════════
   THEME-AWARE FOUNDATION
   Works with Streamlit Light + Dark Mode
═══════════════════════════════════════════════════════ */

:root {
    --radius: 12px;
}

/* App background */
[data-testid="stAppViewContainer"] {
    background-color: var(--background-color);
}

/* Main content */
.main {
    background-color: var(--background-color);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: var(--secondary-background-color) !important;
    border-right: 1px solid rgba(128,128,128,0.12);
}

section[data-testid="stSidebar"] > div {
    background-color: var(--secondary-background-color);
}

/* Global text */
html, body, p, li, label, div, span {
    color: var(--text-color);
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
    color: var(--text-color) !important;
}

/* Links */
a {
    color: #1f6feb !important;
}

/* ═══════════════════════════════════════════════════════
   KPI METRIC CARDS
═══════════════════════════════════════════════════════ */

div[data-testid="stMetric"] {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.15);
    border-radius: var(--radius);
    padding: 18px 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}

/* Metric label */
div[data-testid="stMetricLabel"] > div {
    color: rgba(128,128,128,0.9) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    letter-spacing: 0.3px;
}

/* Metric value */
div[data-testid="stMetricValue"] > div {
    color: var(--text-color) !important;
    font-size: 26px !important;
    font-weight: 700 !important;
}

/* Metric delta */
div[data-testid="stMetricDelta"] > div {
    font-size: 11px !important;
}

/* ═══════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════ */

.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--secondary-background-color);
    padding: 4px;
    border-radius: 10px;
    border: 1px solid rgba(128,128,128,0.12);
}

.stTabs [data-baseweb="tab"] {
    height: 42px;
    font-weight: 600;
    font-size: 13px;
    border-radius: 8px;
    background: transparent;
    border: none !important;
    color: rgba(128,128,128,0.85);
}

.stTabs [aria-selected="true"] {
    background: rgba(31,111,235,0.12) !important;
    color: #1f6feb !important;
    border: 1px solid rgba(31,111,235,0.25) !important;
}

/* ═══════════════════════════════════════════════════════
   SECTION HEADER
═══════════════════════════════════════════════════════ */

.sec-hdr {
    font-size: 11px;
    font-weight: 700;
    color: rgba(128,128,128,0.85);
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid rgba(128,128,128,0.15);
    padding-bottom: 6px;
    margin: 18px 0 12px 0;
}

/* ═══════════════════════════════════════════════════════
   ALERT BOXES
═══════════════════════════════════════════════════════ */

.alert-info {
    background: rgba(31,111,235,0.08);
    border-left: 4px solid #1f6feb;
    border-radius: 8px;
    padding: 12px 14px;
    margin: 8px 0;
    font-size: 13px;
    color: var(--text-color);
}

.alert-warn {
    background: rgba(210,153,34,0.10);
    border-left: 4px solid #d29922;
    border-radius: 8px;
    padding: 12px 14px;
    margin: 8px 0;
    font-size: 13px;
    color: var(--text-color);
}

/* ═══════════════════════════════════════════════════════
   SIDEBAR CARDS
═══════════════════════════════════════════════════════ */

.sb-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.15);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 10px;
}

.sb-card .lbl {
    font-size: 10px;
    color: rgba(128,128,128,0.85);
    font-weight: 500;
}

.sb-card .val {
    font-size: 15px;
    color: var(--text-color);
    font-weight: 700;
    margin-top: 2px;
}

/* ═══════════════════════════════════════════════════════
   DATAFRAMES
═══════════════════════════════════════════════════════ */

div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid rgba(128,128,128,0.12);
}

/* ═══════════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════════ */

.stButton > button {
    border-radius: 10px;
    border: 1px solid rgba(128,128,128,0.18);
    transition: all 0.2s ease;
}

.stButton > button:hover {
    border-color: #1f6feb;
}

/* ═══════════════════════════════════════════════════════
   INPUTS
═══════════════════════════════════════════════════════ */

.stSelectbox,
.stMultiSelect,
.stTextInput,
.stNumberInput {
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>

/* Hide multipage navigation menu */
[data-testid="stSidebarNav"] {
    display: none;
}

/* Hide top hamburger menu (optional) */
[data-testid="collapsedControl"] {
    display: none;
}

</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# PLOTLY DARK THEME
# ═══════════════════════════════════════════════════════════
DARK = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#c9d1d9", family="Inter, system-ui, sans-serif", size=12),
    xaxis=dict(gridcolor="#21262d", linecolor="#30363d", tickcolor="#8b949e",
               title_font=dict(size=11), tickfont=dict(size=10)),
    yaxis=dict(gridcolor="#21262d", linecolor="#30363d", tickcolor="#8b949e",
               title_font=dict(size=11), tickfont=dict(size=10)),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#30363d",
                font=dict(size=11)),
    margin=dict(l=0, r=0, t=36, b=0),
    hoverlabel=dict(bgcolor="#161b22", bordercolor="#30363d",
                    font=dict(color="#e6edf3", size=12)),
)
C = ["#58a6ff","#3fb950","#f0883e","#d2a8ff","#ffa657",
     "#ff7b72","#79c0ff","#56d364","#e3b341","#bc8cff"]


def dark(**overrides) -> dict:
    d = dict(DARK)
    d.update(overrides)
    return d
# ═══════════════════════════════════════════════════════════
# DATA LOADING  (cached)
# ═══════════════════════════════════════════════════════════
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_all_data():
    if not DB_PATH.exists():
        return None

    users  = load_users()
    logs   = load_usage_logs()
    jira   = load_jira()
    github = load_github()

    enriched     = enrich_usage_logs(logs, users)
    dept_perf    = compute_dept_performance(jira)
    user_summary = compute_user_summary(logs, jira, users, github)
    classified   = classify_users(user_summary)
    opt_summary  = optimisation_summary(classified)
    kpis         = executive_kpis(logs, jira, user_summary)
    monthly      = monthly_trend_analysis(logs, jira)
    bench        = benchmark_departments(classified)
    velocity     = velocity_analysis(jira)
    thruput      = compute_throughput_delta(velocity)
    correlations = spend_vs_productivity_analysis(classified)

    # GitHub analytics (works on both synthetic and live PR data)
    gh_enrich   = ensure_period_column(enrich_department(github)) if not github.empty else github
    gh_perf     = pr_performance_summary(gh_enrich)
    gh_delta    = compute_pr_efficiency_delta(gh_perf)
    gh_top      = top_contributors(gh_enrich, n=15)
    gh_repos    = repo_breakdown(gh_enrich)
    gh_monthly  = velocity_trend_monthly(gh_enrich)

    return {
        "users":       users,
        "logs":        logs,
        "enriched":    enriched,
        "jira":        jira,
        "github":      gh_enrich,
        "dept_perf":   dept_perf,
        "user_sum":    user_summary,
        "classified":  classified,
        "opt_summary": opt_summary,
        "kpis":        kpis,
        "monthly":     monthly,
        "bench":       bench,
        "velocity":    velocity,
        "thruput":     thruput,
        "corr":        correlations,
        "gh_perf":     gh_perf,
        "gh_delta":    gh_delta,
        "gh_top":      gh_top,
        "gh_repos":    gh_repos,
        "gh_monthly":  gh_monthly,
    }




# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    # ── DB check ─────────────────────────────────────────
    if not DB_PATH.exists():
        st.error(
            f"**Database not found** at `{DB_PATH}`.\n\n"
            "Run the setup script first:\n"
            "```bash\npython scripts/setup_db.py\n```"
        )
        st.stop()

    with st.spinner("Loading AIFORGE data…"):
        D = load_all_data()

    if D is None:
        st.error("Failed to load data. Check database path in .env")
        st.stop()
    # Working copies used for filtering
    logs       = D["enriched"].copy()
    jira       = D["jira"].copy()
    github     = D["github"].copy()
    classified = D["classified"].copy()
    dept_perf  = D["dept_perf"].copy()

    def pick_date_col(df, candidates):
        for col in candidates:
            if col in df.columns:
                return col
        return None
    def to_datetime_col(df, col):
        if col and col in df.columns:
            s = pd.to_datetime(df[col], errors="coerce", utc=True)
            df[col] = s.dt.tz_localize(None)   # strip tz, keep wall-clock UTC value
        return df
    logs_date_col   = pick_date_col(logs, ["timestamp", "created_at", "created_date", "date"])
    jira_date_col   = pick_date_col(jira, ["created_at", "created_date", "timestamp", "date"])
    github_date_col = pick_date_col(github, ["created_at", "created_date", "timestamp", "date"])

    logs   = to_datetime_col(logs, logs_date_col)
    jira   = to_datetime_col(jira, jira_date_col)
    github = to_datetime_col(github, github_date_col)

    # ── SIDEBAR ──────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 🔷 AIFORGE ANALYTICS")
        st.caption("Enterprise AI Analytics Platform")
        st.divider()

        dept = "All"
        period_opt = "Both"
        st.markdown("### Select Departments")

        if "department" in D["users"].columns:
            all_depts = sorted(
                D["users"]["department"]
                .dropna()
                .unique()
                .tolist()
            )
        else:
            all_depts = []

        selected_depts = []

        for dept_name in all_depts:
            checked = st.checkbox(
                dept_name,
                value=True,
                key=f"dept_{dept_name}"
            )
            if checked:
                selected_depts.append(dept_name)  
        st.divider()
        enable_github = st.toggle(" Enable GitHub toggle ", value=False)      
                
        st.divider()
        if st.button("🔄 Refresh Cache", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── APPLY FILTERS ─────────────────────────────────────
    logs       = D["enriched"].copy()
    jira       = D["jira"].copy()
    classified = D["classified"].copy()
    dept_perf  = D["dept_perf"].copy()
    velocity   = D["velocity"].copy()
    thruput    = D["thruput"].copy()

    if dept != "All":
        logs       = logs[logs["department"]       == dept]
        jira       = jira[jira["department"]       == dept]
        classified = classified[classified["department"] == dept]
        dept_perf  = dept_perf[dept_perf["department"] == dept]
        velocity   = velocity[velocity["department"] == dept]
        thruput    = thruput[thruput["department"]  == dept]


    if period_opt != "Both":
        jira     = jira[jira["period"] == period_opt]
        velocity = velocity[velocity["period"] == period_opt]
    if "department" in logs.columns:
        logs = logs[logs["department"].isin(selected_depts)]
    if "department" in jira.columns:
        jira = jira[jira["department"].isin(selected_depts)]
    if "department" in github.columns:
        github = github[github["department"].isin(selected_depts)]


    
    # ── HEADER ────────────────────────────────────────────
    st.markdown("# 🔷 AIFORGE Enterprise Intelligence Dashboard")
    active_users = logs["user_id"].nunique()
    usage_events = len(logs)

    header_text = (
        f"Analysing {usage_events:,} usage events · "
        f"{active_users:,} active users"
    )

    
    header_text += (
        f" · Last Refreshed "
        f"{datetime.now().strftime('%H:%M UTC')}"
    )

    st.caption(header_text)
    # ── KPI STRIP ─────────────────────────────────────────
    before_avg = jira[jira["period"]=="Before"]["cycle_time_hours"].mean() if not jira.empty else 0
    after_avg  = jira[jira["period"]=="After" ]["cycle_time_hours"].mean() if not jira.empty else 0
    pct_imp    = ((before_avg - after_avg) / before_avg * 100) if before_avg > 0 else 0
    gh_matched = int(D["users"]["github_username"].notna().sum())
    opt        = optimisation_summary(classified)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("💰 Total AI Spend", f"${logs['cost_usd'].sum():,.2f}")
    k2.metric("⚡ Cycle Time Improvement", f"{pct_imp:.1f}%")
    total_tokens = logs["token_count"].sum()

    if total_tokens >= 1_000_000:
        token_display = f"{total_tokens / 1_000_000:.1f}M"
    elif total_tokens >= 1_000:
        token_display = f"{total_tokens / 1_000:.1f}K"
    else:
        token_display = f"{total_tokens:,}"

    k3.metric(
        "🔑 Total Tokens Used",
        token_display
    )
    k4.metric("🛡️ High / Critical Risk", f"{len(logs[logs['risk_level'].isin(['High','Critical'])])}")
    k5.metric("🔗 GitHub Matched", f"{gh_matched}")
             


    # ═══════════════════════════════════════════════════
    # TABS
    # ═══════════════════════════════════════════════════
    t1, t2, t3, t4, t5 = st.tabs([
        "📈 Executive Overview",
        "⚙️ Usage Analytics",
        "🚀 Productivity Impact",
        "🔒 Governance & Security",
        "🐙 GitHub Insights",
    ])

    # ───────────────────────────────────────────────────
    # TAB 1 — EXECUTIVE OVERVIEW
    # ───────────────────────────────────────────────────
    with t1:
        st.markdown('<p class="sec-hdr">Financial & Adoption Trends</p>', unsafe_allow_html=True)

        # Daily cost + token trend (dual axis)
        col1, col2 = st.columns([3, 2])
        with col1:
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
                fill="tozeroy", fillcolor="rgba(88,166,255,0.07)"
            ), secondary_y=False)
            fig.add_trace(go.Bar(
                x=trend["date"], y=trend["cost"], name="Cost ($)",
                marker_color="rgba(240,136,62,0.55)",
                marker_line_color="#f0883e", marker_line_width=0.5
            ), secondary_y=True)
            fig.update_layout(title="Daily Token Consumption vs Spend", height=340, **dark())
            fig.update_yaxes(title_text="Token Count", secondary_y=False,
                             gridcolor="#21262d", tickcolor="#8b949e", tickfont=dict(size=10))
            fig.update_yaxes(title_text="Cost USD",    secondary_y=True,
                             gridcolor="rgba(0,0,0,0)", tickcolor="#8b949e", tickfont=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            dept_cost = logs.groupby("department")["cost_usd"].sum().sort_values().reset_index()
            fig2 = px.bar(
                dept_cost, x="cost_usd", y="department", orientation="h",
                title="Spend by Department",
                color="cost_usd", color_continuous_scale=["#0d2137","#1f6feb","#58a6ff"],
                labels={"cost_usd":"Cost (USD)","department":""},
                text="cost_usd",
            )
            fig2.update_layout(height=340, showlegend=False, coloraxis_showscale=False, **dark())
            fig2.update_traces(texttemplate="$%{text:,.0f}", textposition="outside",
                               marker_line_width=0,
                               hovertemplate="%{y}: $%{x:,.2f}<extra></extra>")
            st.plotly_chart(fig2, use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            if "day_name" not in logs.columns:
                logs["day_name"] = pd.to_datetime(logs["timestamp"], errors="coerce").dt.day_name()
            dow = logs.groupby("day_name")["prompt_id"].count().reindex(dow_order).fillna(0).reset_index()
            dow.columns = ["day","events"]
            fig3 = px.bar(
                dow, x="day", y="events", title="Usage Volume by Day of Week",
                color="events", color_continuous_scale=["#0d2137","#3fb950"],
                labels={"day":"","events":"Prompts"},
                text="events",
            )
            fig3.update_layout(height=300, showlegend=False, coloraxis_showscale=False, **dark())
            fig3.update_traces(texttemplate="%{text:,}", textposition="outside",
                               marker_line_width=0,
                               hovertemplate="%{x}: %{y:,} prompts<extra></extra>")
            st.plotly_chart(fig3, use_container_width=True)

        with col4:
            dept_users = logs.groupby("department")["user_id"].nunique().reset_index()
            dept_users.columns = ["department","active_users"]
            fig4 = px.bar(
                dept_users, x="department", y="active_users",
                title="Active Users by Department",
                color="active_users", color_continuous_scale=["#0d2137","#d2a8ff"],
                labels={"department":"","active_users":"Users"},
                text="active_users",
            )
            fig4.update_layout(height=300, showlegend=False, coloraxis_showscale=False, **dark())
            fig4.update_traces(texttemplate="%{text}", textposition="outside",
                               marker_line_width=0,
                               hovertemplate="%{x}: %{y} users<extra></extra>")
            st.plotly_chart(fig4, use_container_width=True)

        # Benchmark table
        st.markdown('<p class="sec-hdr">Department Benchmark</p>', unsafe_allow_html=True)
        bench = D["bench"].copy()
        if dept != "All":
            bench = bench[bench["department"] == dept]
        if not bench.empty:
            display_bench = bench[[c for c in [
                "department","headcount","total_spend",
                "avg_pct_improvement","total_net_roi","zombie_count","zombie_pct"
            ] if c in bench.columns]].copy()
            for c in ["total_spend","total_net_roi"]:
                if c in display_bench.columns:
                    display_bench[c] = display_bench[c].apply(lambda v: f"${v:,.2f}")
            if "avg_pct_improvement" in display_bench.columns:
                display_bench["avg_pct_improvement"] = display_bench["avg_pct_improvement"].apply(lambda v: f"{v:.1f}%")
            st.dataframe(display_bench, use_container_width=True)

    # ───────────────────────────────────────────────────
    # TAB 2 — USAGE ANALYTICS
    # ───────────────────────────────────────────────────
    with t2:
        st.markdown('<p class="sec-hdr">AI Tool & Consumption Patterns</p>', unsafe_allow_html=True)

        col_u1, col_u2 = st.columns(2)

        with col_u1:
            tk = logs[logs["token_count"] > 0]["token_count"]
            fig_tk = px.histogram(
                tk, nbins=40, title="Token Consumption Distribution",
                color_discrete_sequence=["#58a6ff"],
                labels={"value":"Tokens per Request","count":"Frequency"},
            )
            fig_tk.update_layout(height=340, **dark())
            fig_tk.update_traces(marker_line_width=0.5, marker_line_color="#1f6feb",
                                 hovertemplate="Tokens: %{x:,}<br>Count: %{y}<extra></extra>")
            if len(tk) > 0:
                med = tk.median()
                fig_tk.add_vline(x=med, line_dash="dash", line_color="#f0883e",
                                 annotation_text=f"Median: {med:,.0f}",
                                 annotation_font_color="#f0883e",
                                 annotation_position="top right")
            st.plotly_chart(fig_tk, use_container_width=True)

        with col_u2:
            model_agg = (
                logs.groupby("model_name")
                .agg(requests=("prompt_id","count"), total_cost=("cost_usd","sum"))
                .reset_index().sort_values("requests", ascending=False)
            )
            fig_m = px.bar(
                model_agg, x="model_name", y="requests",
                title="Requests per AI Model",
                color="total_cost", color_continuous_scale=["#0d2137","#58a6ff"],
                text="requests",
                labels={"model_name":"Model","requests":"Requests","total_cost":"Cost ($)"},
            )
            fig_m.update_layout(height=340, **dark())
            fig_m.update_traces(texttemplate="%{text:,}", textposition="outside",
                                marker_line_width=0,
                                hovertemplate="%{x}<br>Requests: %{y:,}<br>Cost: $%{customdata[0]:,.2f}<extra></extra>",
                                customdata=model_agg[["total_cost"]].values)
            st.plotly_chart(fig_m, use_container_width=True)

        dm = logs.groupby(["department","model_name"])["cost_usd"].sum().reset_index()
        fig_dm = px.bar(
            dm, x="department", y="cost_usd", color="model_name",
                title="Cost Breakdown: Department × Model",
                color_discrete_sequence=C, barmode="stack",
                labels={"cost_usd":"Cost (USD)","department":"","model_name":"Model"},
            )
        fig_dm.update_layout(height=400, **dark())
        fig_dm.update_traces(marker_line_width=0,
                                 hovertemplate="%{x}<br>%{fullData.name}: $%{y:,.3f}<extra></extra>")
        st.plotly_chart(fig_dm, use_container_width=True)

        # Monthly trend
        st.markdown('<p class="sec-hdr">Month-over-Month Trend</p>', unsafe_allow_html=True)
        monthly = D["monthly"].copy()
        if not monthly.empty:
            fig_mom = make_subplots(specs=[[{"secondary_y": True}]])
            fig_mom.add_trace(go.Bar(
                x=monthly["month_year"], y=monthly["total_cost"],
                name="Cost ($)", marker_color="rgba(88,166,255,0.6)",
                marker_line_width=0
            ), secondary_y=False)
            fig_mom.add_trace(go.Scatter(
                x=monthly["month_year"], y=monthly["active_users"],
                name="Active Users", line=dict(color="#3fb950", width=2),
                mode="lines+markers", marker=dict(size=6)
            ), secondary_y=True)
            fig_mom.update_layout(title="Monthly Spend vs Active Users", height=350, **dark())
            fig_mom.update_yaxes(title_text="Cost ($)",      secondary_y=False)
            fig_mom.update_yaxes(title_text="Active Users",  secondary_y=True,
                                 gridcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_mom, use_container_width=True)

    # ───────────────────────────────────────────────────
    # TAB 3 — PRODUCTIVITY IMPACT
    # ───────────────────────────────────────────────────
    with t3:
        st.markdown('<p class="sec-hdr">Jira Ticket Cycle Time: Before vs After AI</p>',
                    unsafe_allow_html=True)

        ba = D["jira"].copy()
        if dept != "All":
                ba = ba[ba["department"] == dept]
        ba_agg = (
                ba.groupby(["department","period"])["cycle_time_hours"]
                .mean().reset_index()
            )
        ba_agg.columns = ["department","period","mean_hours"]
        ba_agg["mean_hours"] = ba_agg["mean_hours"].round(1)

        fig_ba = px.bar(
                ba_agg, x="department", y="mean_hours", color="period",
                barmode="group", title="Avg Cycle Time: Before vs After (hours)",
                color_discrete_map={"Before":"#f0883e","After":"#3fb950"},
                text="mean_hours",
                labels={"mean_hours":"Avg Hours","department":"","period":"Period"},
            )
        fig_ba.update_layout(height=360, **dark())
        fig_ba.update_traces(
                texttemplate="%{text:.1f}h", textposition="outside",
                marker_line_width=0,
                hovertemplate="%{x}<br>%{fullData.name}: %{y:.1f} hrs<extra></extra>"
            )
        st.plotly_chart(fig_ba, use_container_width=True)

        col_p3, col_p4 = st.columns(2)

        with col_p3:
            sc = D["jira"].copy()
            if dept != "All":
                sc = sc[sc["department"] == dept]
            sc = sc[(sc["story_points"] > 0) & (sc["cycle_time_hours"] > 0)]
            if len(sc) > 5:
                fig_sc = px.scatter(
                    sc, x="story_points", y="cycle_time_hours",
                    color="period", trendline="ols",
                    title="Story Points vs Cycle Time",
                    color_discrete_map={"Before":"#f0883e","After":"#3fb950"},
                    labels={"story_points":"Story Points",
                            "cycle_time_hours":"Cycle Time (h)",
                            "period":"Period"},
                )
                fig_sc.update_layout(height=340, **dark())
                fig_sc.update_traces(
                    hovertemplate="%{x} pts → %{y:.1f}h<extra>%{fullData.name}</extra>"
                )
                # Hide OLS annotation — clean chart
                for trace in fig_sc.data:
                    if "trendline" in str(type(trace)).lower() or trace.mode == "lines":
                        trace.hovertemplate = "%{y:.1f}h<extra>Trend</extra>"
                st.plotly_chart(fig_sc, use_container_width=True)
            else:
                st.info("Not enough data for scatter (need >5 points). Adjust filters.")

        with col_p4:
            pri = D["jira"].copy()
            if dept != "All":
                pri = pri[pri["department"] == dept]
            pri_agg = (
                pri.groupby(["priority","period"])["jira_issue_id"]
                .count().reset_index()
            )
            pri_agg.columns = ["priority","period","count"]
            fig_pri = px.bar(
                pri_agg, x="priority", y="count", color="period",
                barmode="group", title="Tickets by Priority — Before vs After",
                color_discrete_map={"Before":"#f0883e","After":"#3fb950"},
                labels={"priority":"Priority","count":"Tickets","period":"Period"},
                category_orders={"priority":["Low","Medium","High","Critical"]},
            )
            fig_pri.update_layout(height=340, **dark())
            fig_pri.update_traces(
                marker_line_width=0,
                hovertemplate="%{x} | %{fullData.name}: %{y} tickets<extra></extra>"
            )
            st.plotly_chart(fig_pri, use_container_width=True)


        # ── GitHub PR Analytics (live or synthetic) ──────────────────
        st.markdown('<p class="sec-hdr">GitHub PR Analytics — Real Data · Copilot Boundary: 21 Jun 2022</p>',
                    unsafe_allow_html=True)

        gh_delta   = D["gh_delta"].copy()
        gh_top     = D["gh_top"].copy()
        gh_repos   = D["gh_repos"].copy()
        gh_monthly = D["gh_monthly"].copy()
        gh_data    = D["github"].copy()

        if dept != "All":
            gh_delta   = gh_delta[gh_delta["department"]   == dept] if not gh_delta.empty and "department" in gh_delta.columns else gh_delta
            gh_repos   = gh_repos[gh_repos["department"]   == dept] if not gh_repos.empty and "department" in gh_repos.columns else gh_repos
            gh_monthly = gh_monthly[gh_monthly["department"] == dept] if not gh_monthly.empty and "department" in gh_monthly.columns else gh_monthly
            gh_data    = gh_data[gh_data["department"]     == dept] if not gh_data.empty and "department" in gh_data.columns else gh_data
            gh_top     = gh_top[gh_top["department"]       == dept] if not gh_top.empty and "department" in gh_top.columns else gh_top

        if gh_data.empty:
            st.markdown("""<div class="alert-info">
                ℹ️ <b>Synthetic GitHub data</b> is shown below. To see live PR data, run:<br>
                <code>python scripts/run_pipeline.py --mode live</code>
            </div>""", unsafe_allow_html=True)

        
        col_gh3, col_gh4 = st.columns(2)

        with col_gh3:
            if not gh_monthly.empty and "month" in gh_monthly.columns:
                fig_ghm = px.line(
                    gh_monthly, x="month", y="avg_cycle", color="department",
                    title="Monthly PR Cycle Time Trend by Department",
                    color_discrete_sequence=C,
                    labels={"month": "Month", "avg_cycle": "Avg Hours", "department": "Dept"},
                    markers=False,
                )
                # Mark Copilot launch
                copilot_date = pd.to_datetime(COPILOT_LAUNCH_DATE)

                fig_ghm.add_vline(
                    x=copilot_date,
                    line_dash="dash",
                    line_color="#f0883e",
                )

                fig_ghm.add_annotation(
                    x=copilot_date,
                    y=gh_monthly["avg_cycle"].max(),
                    text="Copilot Launch",
                    showarrow=True,
                    arrowhead=2,
                    font=dict(color="#f0883e")

                )
                fig_ghm.update_layout(height=300, **dark())
                fig_ghm.update_traces(
                    hovertemplate="%{x}: %{y:.1f}h<extra>%{fullData.name}</extra>",
                    line=dict(width=1.5)
                )
                st.plotly_chart(fig_ghm, use_container_width=True)

        with col_gh4:
            if not gh_data.empty and "rework_ratio" in gh_data.columns:
                rw = gh_data.groupby(["department", "period"])["rework_ratio"].mean().reset_index()
                fig_rw = px.bar(
                    rw, x="department", y="rework_ratio", color="period",
                    barmode="group",
                    title="Code Rework Ratio by Department (Lower = Better)",
                    color_discrete_map={"Before": "#f0883e", "After": "#3fb950"},
                    text="rework_ratio",
                    labels={"rework_ratio": "Rework Ratio", "department": "", "period": "Period"},
                )
                fig_rw.update_layout(height=300, **dark())
                fig_rw.update_traces(
                    texttemplate="%{text:.3f}", textposition="outside",
                    marker_line_width=0,
                    hovertemplate="%{x} | %{fullData.name}: %{y:.3f}<extra></extra>"
                )
                st.plotly_chart(fig_rw, use_container_width=True)

        # Repo breakdown table
        st.markdown('<p class="sec-hdr">Repository Breakdown — PR Volume & Cycle Time</p>',
                    unsafe_allow_html=True)
        if not gh_repos.empty:
            disp_repos = gh_repos.copy()
            if "avg_cycle" in disp_repos.columns:
                disp_repos["avg_cycle"] = disp_repos["avg_cycle"].apply(lambda v: f"{v:.1f}h")
            if "avg_rework" in disp_repos.columns:
                disp_repos["avg_rework"] = disp_repos["avg_rework"].apply(lambda v: f"{v:.3f}")
            st.dataframe(disp_repos, use_container_width=True, height=280)

        

    # ───────────────────────────────────────────────────
    # TAB 4 — GOVERNANCE & SECURITY
    # ───────────────────────────────────────────────────
    with t4:
        st.markdown('<p class="sec-hdr">Risk & Security Analysis</p>', unsafe_allow_html=True)

        risk_df = logs[logs["risk_score"] > 0].copy()

        col_g1, col_g2, = st.columns(2)

        # Gauge
        with col_g1:
            avg_risk    = risk_df["risk_score"].mean() if not risk_df.empty else 0
            risk_colour = "#3fb950" if avg_risk < 30 else ("#f0883e" if avg_risk < 70 else "#ff7b72")
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=round(avg_risk, 1),
                number={"suffix":"", "font":{"color":"#e6edf3","size":30}},
                title={"text":"Corporate Risk Index","font":{"color":"#8b949e","size":13}},
                gauge={
                    "axis":  {"range":[0,100],"tickcolor":"#8b949e","tickwidth":1,
                              "tickfont":{"size":9}},
                    "bar":   {"color":risk_colour,"thickness":0.25},
                    "steps": [
                        {"range":[0,30],   "color":"rgba(63,185,80,0.12)"},
                        {"range":[30,70],  "color":"rgba(240,136,62,0.12)"},
                        {"range":[70,100], "color":"rgba(255,123,114,0.12)"},
                    ],
                    "threshold": {"line":{"color":"#ff7b72","width":2},
                                  "thickness":0.75,"value":70},
                    "bgcolor":"rgba(0,0,0,0)","bordercolor":"#30363d",
                }
            ))
            fig_gauge.update_layout(
                height=310, paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#c9d1d9"),
                margin=dict(l=20,r=20,t=40,b=20)
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        # Treemap
        with col_g2:
            if not risk_df.empty:
                rt = risk_df.groupby(["department","risk_level"])["risk_score"].sum().reset_index()
                rt["root"] = "Enterprise"
                fig_tree = px.treemap(
                    rt, path=["root","department","risk_level"],
                    values="risk_score", title="Risk Exposure Hierarchy",
                    color="risk_score",
                    color_continuous_scale=["#0d1117","#f0883e","#ff7b72"],
                )
                fig_tree.update_layout(height=310, **dark())
                fig_tree.update_traces(
                    hovertemplate="<b>%{label}</b><br>Risk Score: %{value:.1f}<extra></extra>",
                    marker_line_width=0.5,
                )
                st.plotly_chart(fig_tree, use_container_width=True)
            else:
                st.info("No risk events under current filters.")

        # Removed risk level chart as requested.

        # PII breakdown
        st.markdown('<p class="sec-hdr">PII Detection Breakdown by Department</p>',
                    unsafe_allow_html=True)
        pii_dept = (
            logs[logs["risk_flag"] == 1]
                .groupby("department")["prompt_id"].count()
                .sort_values(ascending=False).reset_index()
            )
        pii_dept.columns = ["department","pii_events"]
        fig_pii = px.bar(
                pii_dept, x="department", y="pii_events",
                title="PII Violation Events by Department",
                color="pii_events",
                color_continuous_scale=["#21262d","#da3633"],
                text="pii_events",
                labels={"department":"","pii_events":"Flagged Prompts"},
            )
        fig_pii.update_layout(height=280, showlegend=False,coloraxis_showscale=False, **dark())
        fig_pii.update_traces(texttemplate="%{text}", textposition="outside",marker_line_width=0,
                    hovertemplate="%{x}: %{y} violations<extra></extra>")
        st.plotly_chart(fig_pii, use_container_width=True)

        # Forensic incident log
        st.markdown('<p class="sec-hdr">Forensic Incident Log — Last 20 Flagged Prompts (Redacted)</p>',
                    unsafe_allow_html=True)
        inc_cols = [c for c in ["user_id","department","model_name",
                                 "risk_level","risk_score","prompt_text",
                                 "timestamp"] if c in risk_df.columns]
        if not risk_df.empty and inc_cols:
            disp = risk_df[inc_cols].nlargest(20, "risk_score").copy()
            if "prompt_text" in disp.columns:
                disp["prompt_text"] = disp["prompt_text"].str[:80] + "…"
            if "risk_score" in disp.columns:
                disp["risk_score"] = disp["risk_score"].round(1)
            st.dataframe(disp, use_container_width=True, height=320)
        else:
            st.info("No flagged incidents under current filters.")
    # ───────────────────────────────────────────────────
    # TAB 5 — GITHUB ENGINEERING INTELLIGENCE
    # Real data from 19 public repos · Copilot boundary
    # ───────────────────────────────────────────────────
    with t5:
        st.info(
            "This module uses real GitHub repository data. "
            "Turn on the toggle below to load the analytics."
        )


        if not enable_github:
            st.markdown(
                """
                <div class="alert-info">
                    <b>GitHub Toggle  is turned off.</b><br>
                    Enable the toggle above to view pull request efficiency,
                    Copilot impact, contributor productivity, and repository analytics.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            # Pull GitHub frames
            gh = D["github"].copy()
            gh_delta = D["gh_delta"].copy()
            gh_top = D["gh_top"].copy()
            gh_repos = D["gh_repos"].copy()
            gh_month = D["gh_monthly"].copy()
            gh_perf = D["gh_perf"].copy()

            if dept != "All":
                gh = gh[gh["department"] == dept] if not gh.empty and "department" in gh.columns else gh
                gh_delta = gh_delta[gh_delta["department"] == dept] if not gh_delta.empty and "department" in gh_delta.columns else gh_delta
                gh_top = gh_top[gh_top["department"] == dept] if not gh_top.empty and "department" in gh_top.columns else gh_top
                gh_repos = gh_repos[gh_repos["department"] == dept] if not gh_repos.empty and "department" in gh_repos.columns else gh_repos
                gh_month = gh_month[gh_month["department"] == dept] if not gh_month.empty and "department" in gh_month.columns else gh_month
                gh_perf = gh_perf[gh_perf["department"] == dept] if not gh_perf.empty and "department" in gh_perf.columns else gh_perf

            # Data source notice
            is_synthetic = (
                gh.empty
                or "repo_full_name" not in gh.columns
                or gh.get("repo_full_name", "").eq("unknown/unknown").all()
                if not gh.empty else True
            )

            if is_synthetic or gh.empty:
                st.markdown(
                    """
                    <div class="alert-info">
                        ℹ️ <b>Showing synthetic GitHub data.</b> To load real PR data from 19 public repos, run:<br>
                        <code style="background:#21262d;padding:2px 6px;border-radius:3px;font-size:11px">
                        python scripts/run_pipeline.py --mode live</code>
                        &nbsp;— takes ~3 minutes, requires GITHUB_TOKEN in .env
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # KPI Strip
            total_prs = len(gh[gh.get("pr_state", "") == "merged"]) if not gh.empty and "pr_state" in gh.columns else len(gh)
            before_cyc = gh[gh["period"] == "Before"]["cycle_time_hours"].mean() if not gh.empty and "period" in gh.columns else 0
            after_cyc = gh[gh["period"] == "After"]["cycle_time_hours"].mean() if not gh.empty and "period" in gh.columns else 0
            cyc_imp = ((before_cyc - after_cyc) / before_cyc * 100) if before_cyc > 0 else 0
            before_rw = gh[gh["period"] == "Before"]["rework_ratio"].mean() if not gh.empty and "period" in gh.columns else 0
            after_rw = gh[gh["period"] == "After"]["rework_ratio"].mean() if not gh.empty and "period" in gh.columns else 0
            rw_imp = ((before_rw - after_rw) / before_rw * 100) if before_rw > 0 else 0
            contributors = gh["github_username"].nunique() if not gh.empty and "github_username" in gh.columns else 0
            repos_count = gh["repo_name"].nunique() if not gh.empty and "repo_name" in gh.columns else 0

            g1, g2, g3, g4, g5 = st.columns(5)
            g1.metric("🔀 PRs Merged", f"{total_prs:,}")
            g2.metric("⚡ Cycle Time Improvement", f"{cyc_imp:.1f}%")
            g3.metric("♻️ Rework Ratio Drop", f"{rw_imp:.1f}%")
            g4.metric("👥 Contributors Tracked", f"{contributors:,}")
            g5.metric("📦 Repos Analysed", f"{repos_count}", delta="19 public OSS repos")

            st.divider()

            # Row 1: Monthly trend
            st.markdown(
                '<p class="sec-hdr">Monthly PR Cycle Time Trend — With Copilot Launch Marker</p>',
                unsafe_allow_html=True
            )

            if not gh_month.empty and "month" in gh_month.columns and "avg_cycle" in gh_month.columns:
                fig_trend = px.line(
                    gh_month,
                    x="month",
                    y="avg_cycle",
                    color="department",
                    title="Avg PR Merge Time by Department (hours) — Monthly",
                    color_discrete_sequence=C,
                    labels={"month": "Month", "avg_cycle": "Avg Merge Time (h)", "department": "Dept"},
                    markers=False,
                )

                copilot_date = pd.to_datetime(COPILOT_LAUNCH_DATE)

                fig_trend.add_vline(
                    x=copilot_date,
                    line_dash="dash",
                    line_color="#f0883e",
                )

                fig_trend.add_annotation(
                    x=copilot_date,
                    y=gh_month["avg_cycle"].max(),
                    text="Copilot Launch",
                    showarrow=True,
                    arrowhead=2,
                    font=dict(color="#f0883e"),
                )

                fig_trend.update_layout(height=320, **dark())
                fig_trend.update_traces(
                    line=dict(width=2),
                    hovertemplate="%{x}<br>%{y:.1f}h<extra>%{fullData.name}</extra>"
                )
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("Monthly trend data not available. Run the pipeline to generate.")

            # Row 2: Cycle time improvement + Before/After bar
            st.markdown(
                '<p class="sec-hdr">Before vs After GitHub Copilot — Cycle Time Analysis</p>',
                unsafe_allow_html=True
            )
            col_r2a, col_r2b = st.columns(2)

            with col_r2a:
                if not gh_delta.empty and "pct_improvement" in gh_delta.columns:
                    fig_imp = px.bar(
                        gh_delta.sort_values("pct_improvement"),
                        x="pct_improvement",
                        y="department",
                        orientation="h",
                        title="PR Cycle Time Improvement per Department (%)",
                        color="pct_improvement",
                        color_continuous_scale=["#21262d", "#3fb950"],
                        text="pct_improvement",
                        labels={"pct_improvement": "% Faster", "department": ""},
                    )
                    fig_imp.update_layout(
                        height=340,
                        showlegend=False,
                        coloraxis_showscale=False,
                        **dark()
                    )
                    fig_imp.update_traces(
                        texttemplate="%{text:.1f}%",
                        textposition="outside",
                        marker_line_width=0,
                        hovertemplate="%{y}: %{x:.1f}% faster after Copilot<extra></extra>"
                    )
                    st.plotly_chart(fig_imp, use_container_width=True)

            with col_r2b:
                if not gh_delta.empty and "before_avg" in gh_delta.columns and "after_avg" in gh_delta.columns:
                    melt = gh_delta.melt(
                        id_vars=["department"],
                        value_vars=["before_avg", "after_avg"],
                        var_name="period",
                        value_name="avg_hours"
                    )
                    melt["period"] = melt["period"].map(
                        {"before_avg": "Before Copilot", "after_avg": "After Copilot"}
                    )
                    melt["avg_hours"] = melt["avg_hours"].round(1)

                    fig_ba = px.bar(
                        melt,
                        x="department",
                        y="avg_hours",
                        color="period",
                        barmode="group",
                        title="Avg PR Merge Time: Before vs After (hours)",
                        color_discrete_map={
                            "Before Copilot": "#f0883e",
                            "After Copilot": "#3fb950"
                        },
                        text="avg_hours",
                        labels={"avg_hours": "Avg Hours", "department": "", "period": "Period"},
                    )
                    fig_ba.update_layout(height=340, **dark())
                    fig_ba.update_traces(
                        texttemplate="%{text:.1f}h",
                        textposition="outside",
                        marker_line_width=0,
                        hovertemplate="%{x} | %{fullData.name}: %{y:.1f}h<extra></extra>"
                    )
                    st.plotly_chart(fig_ba, use_container_width=True)

            # Row 3: Rework ratio
            st.markdown(
                '<p class="sec-hdr">Code Quality Signal & Repository Activity</p>',
                unsafe_allow_html=True
            )

            if not gh_delta.empty and "before_rework" in gh_delta.columns:
                rw_melt = gh_delta.melt(
                    id_vars=["department"],
                    value_vars=["before_rework", "after_rework"],
                    var_name="period",
                    value_name="rework_ratio"
                )
                rw_melt["period"] = rw_melt["period"].map(
                    {"before_rework": "Before Copilot", "after_rework": "After Copilot"}
                )
                rw_melt["rework_ratio"] = rw_melt["rework_ratio"].round(3)

                fig_rw = px.bar(
                    rw_melt,
                    x="department",
                    y="rework_ratio",
                    color="period",
                    barmode="group",
                    title="Rework Ratio Before vs After (lower = better code quality)",
                    color_discrete_map={
                        "Before Copilot": "#f0883e",
                        "After Copilot": "#3fb950"
                    },
                    text="rework_ratio",
                    labels={"rework_ratio": "Rework Ratio", "department": "", "period": "Period"},
                )
                fig_rw.update_layout(height=320, **dark())
                fig_rw.update_traces(
                    texttemplate="%{text:.3f}",
                    textposition="outside",
                    marker_line_width=0,
                    hovertemplate="%{x} | %{fullData.name}: %{y:.3f}<extra></extra>"
                )
                st.plotly_chart(fig_rw, use_container_width=True)

            # Row 4: Throughput + review depth
            st.markdown(
                '<p class="sec-hdr">PR Throughput Trend & Review Depth Analysis</p>',
                unsafe_allow_html=True
            )
            col_r4a, col_r4b = st.columns(2)

            with col_r4a:
                if not gh_month.empty and "pr_count" in gh_month.columns:
                    monthly_total = (
                        gh_month.groupby("month")["pr_count"].sum().reset_index()
                        .sort_values("month")
                    )
                    monthly_total["month"] = pd.to_datetime(monthly_total["month"], errors="coerce")

                    fig_thru = px.area(
                        monthly_total,
                        x="month",
                        y="pr_count",
                        title="Total PRs Merged per Month (All Repos)",
                        color_discrete_sequence=["#58a6ff"],
                        labels={"month": "Month", "pr_count": "PRs Merged"},
                    )

                    copilot_date = pd.to_datetime("2022-06-01")

                    fig_thru.add_vline(
                        x=copilot_date,
                        line_dash="dash",
                        line_color="#f0883e",
                        line_width=2,
                    )

                    fig_thru.add_annotation(
                        x=copilot_date,
                        y=monthly_total["pr_count"].max(),
                        text="Copilot →",
                        showarrow=True,
                        arrowhead=2,
                        font=dict(color="#f0883e"),
                    )

                    fig_thru.update_layout(height=300, **dark())
                    fig_thru.update_traces(
                        fillcolor="rgba(88,166,255,0.1)",
                        line=dict(width=2),
                        hovertemplate="%{x}: %{y:,} PRs<extra></extra>"
                    )
                    st.plotly_chart(fig_thru, use_container_width=True)

            with col_r4b:
                if not gh.empty and "review_count" in gh.columns and "cycle_time_hours" in gh.columns:
                    sc_data = gh[
                        (gh["cycle_time_hours"] > 0) &
                        (gh["cycle_time_hours"] < 500) &
                        (gh["review_count"] >= 0)
                    ].copy()

                    fig_rev = px.scatter(
                        sc_data.sample(min(600, len(sc_data)), random_state=42),
                        x="review_count",
                        y="cycle_time_hours",
                        color="department",
                        title="Review Depth vs PR Cycle Time",
                        color_discrete_sequence=C,
                        opacity=0.6,
                        labels={
                            "review_count": "Review Comments",
                            "cycle_time_hours": "Cycle Time (h)",
                            "department": "Dept",
                        },
                        trendline="ols",
                    )
                    fig_rev.update_layout(height=300, **dark())
                    fig_rev.update_traces(
                        marker=dict(size=5, line=dict(width=0)),
                        hovertemplate="%{x} reviews → %{y:.1f}h<extra>%{fullData.name}</extra>"
                    )
                    st.plotly_chart(fig_rev, use_container_width=True)

            # Top contributors table
            st.markdown(
                '<p class="sec-hdr">Top 15 Contributors — Ranked by PRs Merged</p>',
                unsafe_allow_html=True
            )
            if not gh_top.empty:
                disp_top = gh_top.copy()
                if "avg_cycle" in disp_top.columns:
                    disp_top["avg_cycle"] = disp_top["avg_cycle"].apply(lambda v: f"{v:.1f}h")
                if "avg_rework" in disp_top.columns:
                    disp_top["avg_rework"] = disp_top["avg_rework"].apply(lambda v: f"{v:.3f}")
                if "total_lines" in disp_top.columns:
                    disp_top["total_lines"] = disp_top["total_lines"].apply(lambda v: f"{int(v):,}")
                st.dataframe(disp_top, use_container_width=True)

            # Efficiency delta table
            st.markdown(
                '<p class="sec-hdr">Department Efficiency Delta Summary</p>',
                unsafe_allow_html=True
            )
            if not gh_delta.empty:
                st.dataframe(
                    gh_delta.style.format({
                        "before_avg": "{:.1f}h",
                        "after_avg": "{:.1f}h",
                        "hours_saved": "{:.1f}h",
                        "pct_improvement": "{:.1f}%",
                        "before_rework": "{:.3f}",
                        "after_rework": "{:.3f}",
                        "rework_improvement_pct": "{:.1f}%",
                    }),
                    use_container_width=True,
                    height=300,
                )

if __name__ == "__main__":
    main()
