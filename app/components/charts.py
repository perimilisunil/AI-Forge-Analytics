"""
app/components/charts.py
─────────────────────────
Reusable Plotly chart factory.
All charts share the same dark theme and hover conventions.
Import these in page modules instead of writing px.* inline.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Shared dark theme ────────────────────────────────────
DARK = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#c9d1d9", family="Inter, system-ui, sans-serif", size=12),
    xaxis=dict(gridcolor="#21262d", linecolor="#30363d", tickcolor="#8b949e",
               title_font=dict(size=11), tickfont=dict(size=10)),
    yaxis=dict(gridcolor="#21262d", linecolor="#30363d", tickcolor="#8b949e",
               title_font=dict(size=11), tickfont=dict(size=10)),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#30363d", font=dict(size=11)),
    margin=dict(l=0, r=0, t=36, b=0),
    hoverlabel=dict(bgcolor="#161b22", bordercolor="#30363d",
                    font=dict(color="#e6edf3", size=12)),
)

C = ["#58a6ff","#3fb950","#f0883e","#d2a8ff","#ffa657",
     "#ff7b72","#79c0ff","#56d364","#e3b341","#bc8cff"]


def _d(**overrides) -> dict:
    d = dict(DARK)
    d.update(overrides)
    return d


# ── Chart factories ──────────────────────────────────────

def dual_axis_trend(
    df: pd.DataFrame,
    x: str, bar_y: str, line_y: str,
    bar_label: str = "Cost ($)", line_label: str = "Tokens",
    title: str = "Trend", height: int = 340,
) -> go.Figure:
    """Dual-axis: bar (secondary) + area line (primary)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=df[x], y=df[line_y], name=line_label,
        line=dict(color="#58a6ff", width=2),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.07)",
        hovertemplate=f"{line_label}: %{{y:,}}<extra></extra>"
    ), secondary_y=False)
    fig.add_trace(go.Bar(
        x=df[x], y=df[bar_y], name=bar_label,
        marker_color="rgba(240,136,62,0.55)",
        marker_line_color="#f0883e", marker_line_width=0.5,
        hovertemplate=f"{bar_label}: $%{{y:,.3f}}<extra></extra>"
    ), secondary_y=True)
    fig.update_layout(title=title, height=height, **_d())
    fig.update_yaxes(title_text=line_label, secondary_y=False,
                     gridcolor="#21262d", tickfont=dict(size=10))
    fig.update_yaxes(title_text=bar_label, secondary_y=True,
                     gridcolor="rgba(0,0,0,0)", tickfont=dict(size=10))
    return fig


def horizontal_bar(
    df: pd.DataFrame, x: str, y: str,
    title: str = "", height: int = 340,
    color_scale: list = None,
) -> go.Figure:
    cs = color_scale or ["#0d2137","#1f6feb","#58a6ff"]
    fig = px.bar(
        df, x=x, y=y, orientation="h",
        title=title, color=x,
        color_continuous_scale=cs,
        text=x,
    )
    fig.update_layout(height=height, showlegend=False,
                      coloraxis_showscale=False, **_d())
    fig.update_traces(
        texttemplate="$%{text:,.0f}", textposition="outside",
        marker_line_width=0,
        hovertemplate="%{y}: $%{x:,.2f}<extra></extra>"
    )
    return fig


def grouped_bar_before_after(
    df: pd.DataFrame, x: str, y: str,
    period_col: str = "period",
    title: str = "Before vs After",
    height: int = 360,
) -> go.Figure:
    fig = px.bar(
        df, x=x, y=y, color=period_col, barmode="group",
        title=title,
        color_discrete_map={"Before":"#f0883e","After":"#3fb950"},
        text=y,
    )
    fig.update_layout(height=height, **_d())
    fig.update_traces(
        texttemplate="%{text:.1f}h", textposition="outside",
        marker_line_width=0,
        hovertemplate="%{x} | %{fullData.name}: %{y:.1f} hrs<extra></extra>"
    )
    return fig


def usage_heatmap(df: pd.DataFrame, title: str = "Heatmap",
                  height: int = 300) -> go.Figure:
    """Day-of-week × Hour heatmap."""
    fig = px.imshow(
        df, title=title,
        color_continuous_scale=["#0d1117","#1f6feb","#58a6ff","#f0883e"],
        labels={"color":"Tokens","x":"Hour (UTC)","y":"Day"},
        aspect="auto",
    )
    fig.update_layout(height=height, **_d())
    fig.update_traces(
        hovertemplate="%{y} %{x}:00 — %{z:,} tokens<extra></extra>"
    )
    return fig


def risk_gauge(value: float, title: str = "Corporate Risk Index",
               height: int = 310) -> go.Figure:
    colour = "#3fb950" if value < 30 else ("#f0883e" if value < 70 else "#ff7b72")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(value, 1),
        number={"font": {"color":"#e6edf3","size":30}},
        title={"text": title, "font":{"color":"#8b949e","size":13}},
        gauge={
            "axis":  {"range":[0,100],"tickcolor":"#8b949e","tickwidth":1,
                      "tickfont":{"size":9}},
            "bar":   {"color":colour,"thickness":0.25},
            "steps": [
                {"range":[0,30],   "color":"rgba(63,185,80,0.12)"},
                {"range":[30,70],  "color":"rgba(240,136,62,0.12)"},
                {"range":[70,100], "color":"rgba(255,123,114,0.12)"},
            ],
            "threshold": {"line":{"color":"#ff7b72","width":2},
                          "thickness":0.75,"value":70},
            "bgcolor":"rgba(0,0,0,0)", "bordercolor":"#30363d",
        }
    ))
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9"),
        margin=dict(l=20,r=20,t=40,b=20)
    )
    return fig


def risk_treemap(df: pd.DataFrame, path: list, values: str,
                 title: str = "Risk Hierarchy",
                 height: int = 310) -> go.Figure:
    fig = px.treemap(
        df, path=path, values=values, title=title,
        color=values,
        color_continuous_scale=["#0d1117","#f0883e","#ff7b72"],
    )
    fig.update_layout(height=height, **_d())
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Risk Score: %{value:.1f}<extra></extra>",
        marker_line_width=0.5,
    )
    return fig


def scatter_with_ols(
    df: pd.DataFrame, x: str, y: str,
    color: str = None, title: str = "Scatter",
    height: int = 340,
) -> go.Figure:
    kwargs = dict(trendline="ols")
    if color:
        kwargs["color"] = color
        kwargs["color_discrete_map"] = {"Before":"#f0883e","After":"#3fb950"}
    fig = px.scatter(df, x=x, y=y, title=title, **kwargs)
    fig.update_layout(height=height, **_d())
    fig.update_traces(
        hovertemplate="%{x:.1f} → %{y:.1f}<extra>%{fullData.name}</extra>"
    )
    return fig


def stacked_cost_bar(
    df: pd.DataFrame, x: str, y: str, color: str,
    title: str = "Cost Breakdown", height: int = 300,
) -> go.Figure:
    fig = px.bar(
        df, x=x, y=y, color=color, barmode="stack",
        title=title, color_discrete_sequence=C,
    )
    fig.update_layout(height=height, **_d())
    fig.update_traces(
        marker_line_width=0,
        hovertemplate="%{x} | %{fullData.name}: $%{y:,.3f}<extra></extra>"
    )
    return fig


def token_histogram(series: pd.Series, title: str = "Token Distribution",
                    height: int = 340) -> go.Figure:
    fig = px.histogram(
        series[series > 0], nbins=40, title=title,
        color_discrete_sequence=["#58a6ff"],
        labels={"value":"Tokens per Request","count":"Frequency"},
    )
    fig.update_layout(height=height, **_d())
    fig.update_traces(
        marker_line_width=0.5, marker_line_color="#1f6feb",
        hovertemplate="Tokens: %{x:,}<br>Count: %{y}<extra></extra>"
    )
    if len(series) > 0:
        med = series.median()
        fig.add_vline(
            x=med, line_dash="dash", line_color="#f0883e",
            annotation_text=f"Median: {med:,.0f}",
            annotation_font_color="#f0883e",
            annotation_position="top right"
        )
    return fig
