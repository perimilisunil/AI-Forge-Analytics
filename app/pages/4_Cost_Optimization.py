"""
app/pages/4_Cost_Optimization.py
──────────────────────────────────
Licence Intelligence page — 5-category AI Workforce Optimisation.
Categories: Champion · Healthy · Underutilized · At-Risk · Zombie
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
from src.data.preprocessor import enrich_usage_logs, compute_user_summary
from src.analysis.optimizer import (
    classify_users, optimisation_summary, category_distribution,
    top_performers_table, zombies_table, at_risk_table,
)
from src.analysis.correlation import spend_vs_productivity_analysis
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Licence Intelligence | AIFORGE",
    layout="wide", page_icon="💸"
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #0d1117; }
[data-testid="stSidebar"]          { background-color: #161b22 !important; }
*, p, label, div { color: #c9d1d9; }
h1, h2, h3       { color: #e6edf3 !important; }
.sec-hdr { font-size:11px; font-weight:600; color:#8b949e; text-transform:uppercase;
    letter-spacing:1.2px; border-bottom:1px solid #21262d;
    padding-bottom:6px; margin:16px 0 12px 0; }
.alert-warn { background:#2d1f00; border-left:4px solid #d29922; border-radius:4px;
    padding:10px 14px; margin:8px 0; color:#e3b341; font-size:12px; }
.alert-ok   { background:#0d2137; border-left:4px solid #3fb950; border-radius:4px;
    padding:10px 14px; margin:8px 0; color:#3fb950; font-size:12px; }
.alert-risk { background:#2d1700; border-left:4px solid #f0883e; border-radius:4px;
    padding:10px 14px; margin:8px 0; color:#f0883e; font-size:12px; }
div[data-testid="stMetric"] { border-radius:12px; padding:18px; border:1px solid #21262d; }
div[data-testid="stMetricLabel"] > div { color:#8b949e !important; font-size:12px !important; }
div[data-testid="stMetricValue"] > div { color:#ffffff !important; font-size:24px !important; font-weight:700 !important; }
</style>
""", unsafe_allow_html=True)

_DARK = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#c9d1d9", size=12),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
    hoverlabel=dict(bgcolor="#161b22", font_color="#e6edf3"),
    margin=dict(l=0, r=0, t=36, b=0),
)
CAT_COLORS = {
    "Champion":      "#3fb950",
    "Healthy":       "#58a6ff",
    "Underutilized": "#e3b341",
    "At-Risk":       "#f0883e",
    "Zombie":        "#ff7b72",
}
CAT_ORDER = ["Champion", "Healthy", "Underutilized", "At-Risk", "Zombie"]
C = ["#58a6ff","#3fb950","#f0883e","#d2a8ff","#ffa657","#ff7b72","#79c0ff","#56d364"]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _load():
    users        = load_users()
    logs         = load_usage_logs()
    jira         = load_jira()
    github       = load_github()
    enriched     = enrich_usage_logs(logs, users)
    user_summary = compute_user_summary(logs, jira, users, github)
    classified   = classify_users(user_summary)
    corr         = spend_vs_productivity_analysis(classified)
    return classified, corr


if not DB_PATH.exists():
    st.error("Database not found. Run: `python scripts/setup_db.py`")
    st.stop()

classified, corr = _load()
opt      = optimisation_summary(classified)
cat_dist = category_distribution(classified)

# ── Header ────────────────────────────────────────────────
st.markdown("# 💸 Licence Intelligence")
st.caption("AI Workforce Optimisation — 5-category classification system")

# ── KPI strip ─────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("⭐ Champions",          f"{opt['champion_count']}",
          delta=f"{opt['healthy_count']} healthy")
k2.metric("💤 Underutilized",      f"{opt['underutil_count']}",
          delta="low spend + low output")
k3.metric("⚠️ At-Risk",           f"{opt['at_risk_count']}",
          delta="high spend · low output")
k4.metric("🧟 Zombie Users",       f"{opt['zombie_count']}",
          delta=f"{opt['zombie_pct']}% of workforce")
k5.metric("💵 Monthly Savings",    f"${opt['total_monthly_saving']:,.2f}",
          delta=f"${opt['annual_saving_projection']:,.0f}/yr")

# ── Alert banners ─────────────────────────────────────────
if opt["zombie_count"] > 0:
    st.markdown(f"""<div class="alert-warn">
        🧟 <b>{opt['zombie_count']} zombie users</b> consuming
        <b>${opt['monthly_saving_zombies']:,.2f}/month</b> with
        zero measurable output. Recommend immediate licence revocation.
    </div>""", unsafe_allow_html=True)
if opt["at_risk_count"] > 0:
    st.markdown(f"""<div class="alert-risk">
        ⚠️ <b>{opt['at_risk_count']} at-risk users</b> — high AI spend
        with low ticket throughput. Recommend coaching or downgrade.
    </div>""", unsafe_allow_html=True)
if opt["zombie_count"] == 0 and opt["at_risk_count"] == 0:
    st.markdown("""<div class="alert-ok">
        ✅ No zombie or at-risk users. Excellent licence utilisation.
    </div>""", unsafe_allow_html=True)

st.divider()

# ── Category bar + scatter ─────────────────────────────────
st.markdown('<p class="sec-hdr">Workforce Classification Overview</p>',
            unsafe_allow_html=True)
col1, col2 = st.columns([1, 2])

with col1:
    fig_cat = px.bar(
        cat_dist, x="count", y="category", orientation="h",
        title="Users by Category",
        color="category", color_discrete_map=CAT_COLORS,
        text="count",
        labels={"count": "Users", "category": ""},
        category_orders={"category": list(reversed(CAT_ORDER))},
    )
    fig_cat.update_layout(height=300, showlegend=False, **_DARK)
    fig_cat.update_traces(
        texttemplate="%{text} (%{customdata[0]:.1f}%)",
        textposition="outside",
        marker_line_width=0,
        customdata=cat_dist[["pct"]].values,
        hovertemplate="%{y}: %{x} users (%{customdata[0]:.1f}%)<extra></extra>"
    )
    st.plotly_chart(fig_cat, use_container_width=True)

with col2:
    valid = classified[classified["total_cost"] >= 0].copy()
    fig_sc = px.scatter(
        valid,
        x="total_cost", y="tickets_closed",
        color="category",
        color_discrete_map=CAT_COLORS,
        title="AI Spend vs Tickets Closed — All Categories",
        labels={
            "total_cost":     "Total AI Cost ($)",
            "tickets_closed": "Tickets Closed (After AI)",
            "category":       "Category",
        },
        category_orders={"category": CAT_ORDER},
        hover_data={c: True for c in
                    ["user_id","department"] if c in valid.columns},
    )
    fig_sc.update_layout(height=300, **_DARK)
    fig_sc.update_traces(
        marker=dict(size=8, opacity=0.8, line=dict(width=0)),
        hovertemplate=(
            "Cost: $%{x:,.2f}<br>Tickets: %{y}"
            "<extra>%{fullData.name}</extra>"
        )
    )
    st.plotly_chart(fig_sc, use_container_width=True)

# ── Zombie + At-Risk bars ──────────────────────────────────
col3, col4 = st.columns(2)

with col3:
    z_df = zombies_table(classified)
    st.markdown('<p class="sec-hdr">🧟 Zombie Users — Reclaimable Spend</p>',
                unsafe_allow_html=True)
    if len(z_df) > 0:
        fig_z = px.bar(
            z_df.head(15), x="user_id", y="total_cost",
            color="department",
            title=f"{len(z_df)} Zombie Users — AI Cost ($)",
            color_discrete_sequence=C, text="total_cost",
            labels={"user_id": "User", "total_cost": "Cost ($)"},
        )
        fig_z.update_layout(height=300, **_DARK)
        fig_z.update_traces(
            texttemplate="$%{text:,.2f}", textposition="outside",
            marker_line_width=0,
            hovertemplate="%{x}: $%{y:,.2f}<extra>%{fullData.name}</extra>"
        )
        st.plotly_chart(fig_z, use_container_width=True)
    else:
        st.markdown('<div class="alert-ok">✅ No zombie users detected.</div>',
                    unsafe_allow_html=True)

with col4:
    ar_df = at_risk_table(classified)
    st.markdown('<p class="sec-hdr">⚠️ At-Risk — High Spend · Low Output</p>',
                unsafe_allow_html=True)
    if len(ar_df) > 0:
        fig_ar = px.scatter(
            ar_df, x="total_cost", y="tickets_closed",
            size="total_cost", color="department",
            title="At-Risk: Spend vs Output",
            color_discrete_sequence=C,
            labels={"total_cost": "AI Cost ($)", "tickets_closed": "Tickets"},
        )
        fig_ar.update_layout(height=300, **_DARK)
        fig_ar.update_traces(
            marker=dict(opacity=0.8, line=dict(width=0)),
        )
        st.plotly_chart(fig_ar, use_container_width=True)
    else:
        st.markdown('<div class="alert-ok">✅ No at-risk users detected.</div>',
                    unsafe_allow_html=True)

# ── ROI regression + Licence breakdown ────────────────────
col5, col6 = st.columns(2)
with col5:
    ols = corr.get("cost_vs_roi", {}).get("ols", {})
    if ols.get("n", 0) > 3:
        ols_df = pd.DataFrame({
            "x": ols["x_values"], "y": ols["y_values"],
            "pred": ols["predicted"]
        })
        r2 = ols.get("r_squared", 0)
        fig_o = go.Figure()
        fig_o.add_trace(go.Scatter(
            x=ols_df["x"], y=ols_df["y"], mode="markers",
            name="Users",
            marker=dict(color="#58a6ff", size=6, opacity=0.7),
            hovertemplate="Spend: $%{x:,.2f}<br>ROI: $%{y:,.2f}<extra></extra>"
        ))
        fig_o.add_trace(go.Scatter(
            x=ols_df["x"], y=ols_df["pred"], mode="lines",
            name="OLS Fit",
            line=dict(color="#f0883e", width=2, dash="dash"),
            hovertemplate="Predicted: $%{y:,.2f}<extra></extra>"
        ))
        fig_o.update_layout(
            title=f"AI Spend → Net ROI (R² = {r2:.3f})",
            xaxis_title="Cost ($)", yaxis_title="Net ROI ($)",
            height=280, **_DARK
        )
        st.plotly_chart(fig_o, use_container_width=True)

with col6:
    if "license_type" in classified.columns:
        lic = (
            classified.groupby(["license_type","category"])
            .agg(users=("user_id","count")).reset_index()
        )
        fig_l = px.bar(
            lic, x="license_type", y="users", color="category",
            title="Users per Licence — by Category",
            color_discrete_map=CAT_COLORS, barmode="stack",
            labels={"license_type": "Licence", "users": "Users"},
            category_orders={"category": CAT_ORDER},
        )
        fig_l.update_layout(height=280, **_DARK)
        fig_l.update_traces(marker_line_width=0)
        st.plotly_chart(fig_l, use_container_width=True)

# ── Top performers ─────────────────────────────────────────
st.markdown('<p class="sec-hdr">⭐ Top 10 Champions — Highest Productivity Lift</p>',
            unsafe_allow_html=True)
top = top_performers_table(classified, n=10)
if not top.empty:
    fmt = {}
    if "pct_improvement"        in top.columns: fmt["pct_improvement"]        = "{:.1f}%"
    if "hours_saved_per_ticket" in top.columns: fmt["hours_saved_per_ticket"] = "{:.2f}h"
    if "net_roi"                in top.columns: fmt["net_roi"]                = "${:,.2f}"
    if "total_cost"             in top.columns: fmt["total_cost"]             = "${:,.2f}"
    st.dataframe(top.style.format(fmt), use_container_width=True)

# ── Detail tables ──────────────────────────────────────────
if len(z_df) > 0:
    st.markdown('<p class="sec-hdr">🧟 Zombie Detail — Action: Revoke Licence</p>',
                unsafe_allow_html=True)
    z_show = z_df.copy()
    if "total_cost" in z_show.columns:
        z_show["total_cost"] = z_show["total_cost"].apply(lambda v: f"${v:,.2f}")
    st.dataframe(z_show, use_container_width=True)

if len(ar_df) > 0:
    st.markdown('<p class="sec-hdr">⚠️ At-Risk Detail — Action: Coach or Downgrade</p>',
                unsafe_allow_html=True)
    ar_show = ar_df.copy()
    for c in ["total_cost","net_roi","potential_saving"]:
        if c in ar_show.columns:
            ar_show[c] = ar_show[c].apply(lambda v: f"${v:,.2f}")
    if "pct_improvement" in ar_show.columns:
        ar_show["pct_improvement"] = ar_show["pct_improvement"].apply(lambda v: f"{v:.1f}%")
    st.dataframe(ar_show, use_container_width=True)
