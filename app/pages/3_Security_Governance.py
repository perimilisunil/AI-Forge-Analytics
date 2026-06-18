"""
app/pages/3_Security_Governance.py
────────────────────────────────────
Standalone page: Security & Governance deep-dive.
PII detection breakdown, risk distribution, forensic incident log.
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, CACHE_TTL
from src.data.loader import load_users, load_usage_logs
from src.data.preprocessor import enrich_usage_logs
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Governance | AIFORGE", layout="wide", page_icon="🔒")

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

CM = {"Low":"#3fb950","Medium":"#f0883e","High":"#ff7b72","Critical":"#da3633"}


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _load():
    users    = load_users()
    logs     = load_usage_logs()
    enriched = enrich_usage_logs(logs, users)
    return enriched


if not DB_PATH.exists():
    st.error("Database not found. Run: `python scripts/setup_db.py`")
    st.stop()

logs = _load()

st.markdown("# 🔒 Security & Governance")

# ── KPIs ─────────────────────────────────────────────────
flagged   = logs[logs["risk_flag"] == 1]
total     = len(logs)
high_crit = logs[logs["risk_level"].isin(["High","Critical"])]
avg_risk  = logs[logs["risk_score"] > 0]["risk_score"].mean() if len(logs) else 0
pii_rate  = round(len(flagged) / max(total, 1) * 100, 1)

k1, k2, k3, k4 = st.columns(4)
k1.metric("🛡️ Avg Risk Score",       f"{avg_risk:.1f} / 100")
k2.metric("🚨 PII Violation Rate",   f"{pii_rate}%",     delta=f"{len(flagged)} flagged prompts")
k3.metric("🔴 High / Critical",      f"{len(high_crit)}", delta=f"of {total:,} total")
k4.metric("🏢 Riskiest Department",
          logs.groupby("department")["risk_score"].mean().idxmax()
          if not logs.empty else "—")

st.divider()

# ── Gauge + Treemap ───────────────────────────────────────
st.markdown('<p class="sec-hdr">Corporate Risk Index & Exposure Hierarchy</p>', unsafe_allow_html=True)
col1, col2 = st.columns([1, 2])

with col1:
    colour = "#3fb950" if avg_risk < 30 else ("#f0883e" if avg_risk < 70 else "#ff7b72")
    fig_g = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(avg_risk, 1),
        number={"font":{"color":"#e6edf3","size":32}},
        title={"text":"Corporate Risk Index","font":{"color":"#8b949e","size":13}},
        gauge={
            "axis":  {"range":[0,100],"tickcolor":"#8b949e","tickfont":{"size":9}},
            "bar":   {"color":colour,"thickness":0.25},
            "steps": [
                {"range":[0,30],   "color":"rgba(63,185,80,0.12)"},
                {"range":[30,70],  "color":"rgba(240,136,62,0.12)"},
                {"range":[70,100], "color":"rgba(255,123,114,0.12)"},
            ],
            "threshold":{"line":{"color":"#ff7b72","width":2},"thickness":0.75,"value":70},
            "bgcolor":"rgba(0,0,0,0)","bordercolor":"#30363d",
        }
    ))
    fig_g.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#c9d1d9"), margin=dict(l=20,r=20,t=40,b=20))
    st.plotly_chart(fig_g, use_container_width=True)

with col2:
    risk_df = logs[logs["risk_score"] > 0].copy()
    if not risk_df.empty:
        rt = risk_df.groupby(["department","risk_level"])["risk_score"].sum().reset_index()
        rt["root"] = "Enterprise"
        fig_t = px.treemap(
            rt, path=["root","department","risk_level"],
            values="risk_score", title="Risk Exposure: Department → Risk Level",
            color="risk_score",
            color_continuous_scale=["#0d1117","#f0883e","#ff7b72"],
        )
        fig_t.update_layout(height=300, **_DARK)
        fig_t.update_traces(
            hovertemplate="<b>%{label}</b><br>Risk Score: %{value:.1f}<extra></extra>",
            marker_line_width=0.5,
        )
        st.plotly_chart(fig_t, use_container_width=True)

# ── Risk distribution charts ──────────────────────────────
st.markdown('<p class="sec-hdr">Risk Level Distribution & PII Violations</p>', unsafe_allow_html=True)
col3, col4, col5 = st.columns(3)

with col3:
    rl = logs.groupby("risk_level")["prompt_id"].count().reset_index()
    rl.columns = ["risk_level","count"]
    fig_rl = px.bar(
        rl.sort_values("count"), x="count", y="risk_level", orientation="h",
        title="Events by Risk Level",
        color="risk_level", color_discrete_map=CM, text="count",
        labels={"count":"Events","risk_level":""},
    )
    fig_rl.update_layout(height=280, showlegend=False, **_DARK)
    fig_rl.update_traces(texttemplate="%{text:,}", textposition="outside",
                         marker_line_width=0,
                         hovertemplate="%{y}: %{x:,} events<extra></extra>")
    st.plotly_chart(fig_rl, use_container_width=True)

with col4:
    pii_dept = (
        logs[logs["risk_flag"] == 1]
        .groupby("department")["prompt_id"].count()
        .sort_values(ascending=False).reset_index()
    )
    pii_dept.columns = ["department","violations"]
    fig_pd = px.bar(
        pii_dept, x="department", y="violations",
        title="PII Violations by Department",
        color="violations", color_continuous_scale=["#21262d","#da3633"],
        text="violations",
        labels={"department":"","violations":"Flagged Prompts"},
    )
    fig_pd.update_layout(height=280, showlegend=False, coloraxis_showscale=False, **_DARK)
    fig_pd.update_traces(texttemplate="%{text}", textposition="outside",
                         marker_line_width=0,
                         hovertemplate="%{x}: %{y} violations<extra></extra>")
    st.plotly_chart(fig_pd, use_container_width=True)

with col5:
    model_risk = (
        logs.groupby("model_name")["risk_score"].mean()
        .sort_values(ascending=False).reset_index()
    )
    fig_mr = px.bar(
        model_risk, x="model_name", y="risk_score",
        title="Avg Risk Score by AI Model",
        color="risk_score", color_continuous_scale=["#21262d","#f0883e"],
        text="risk_score",
        labels={"model_name":"","risk_score":"Avg Risk Score"},
    )
    fig_mr.update_layout(height=280, showlegend=False, coloraxis_showscale=False, **_DARK)
    fig_mr.update_traces(texttemplate="%{text:.1f}", textposition="outside",
                         marker_line_width=0,
                         hovertemplate="%{x}: score %{y:.1f}<extra></extra>")
    st.plotly_chart(fig_mr, use_container_width=True)

# ── Risk score distribution histogram ────────────────────
st.markdown('<p class="sec-hdr">Risk Score Distribution</p>', unsafe_allow_html=True)
scores = logs[logs["risk_score"] > 0]["risk_score"]
if not scores.empty:
    fig_hist = px.histogram(
        scores, nbins=30, title="Distribution of Risk Scores (Flagged Prompts Only)",
        color_discrete_sequence=["#f0883e"],
        labels={"value":"Risk Score","count":"Frequency"},
    )
    fig_hist.update_layout(height=260, **_DARK)
    fig_hist.update_traces(marker_line_width=0.5, marker_line_color="#da3633",
                           hovertemplate="Score: %{x:.0f}<br>Count: %{y}<extra></extra>")
    fig_hist.add_vline(x=scores.mean(), line_dash="dash", line_color="#58a6ff",
                       annotation_text=f"Mean: {scores.mean():.1f}",
                       annotation_font_color="#58a6ff")
    st.plotly_chart(fig_hist, use_container_width=True)

# ── Forensic incident log ─────────────────────────────────
st.markdown('<p class="sec-hdr">Forensic Incident Log — Top 25 Highest Risk (Redacted)</p>',
            unsafe_allow_html=True)
risk_df = logs[logs["risk_score"] > 0].copy()
inc_cols = [c for c in ["user_id","department","model_name","risk_level",
                         "risk_score","prompt_text","timestamp"] if c in risk_df.columns]
if not risk_df.empty:
    disp = risk_df[inc_cols].nlargest(25, "risk_score").copy()
    if "prompt_text" in disp.columns:
        disp["prompt_text"] = disp["prompt_text"].str[:80] + "…"
    if "risk_score" in disp.columns:
        disp["risk_score"] = disp["risk_score"].round(1)
    st.dataframe(disp, use_container_width=True, height=400)
else:
    st.info("No flagged incidents found.")
