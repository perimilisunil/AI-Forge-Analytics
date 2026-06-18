"""
app/components/kpi_cards.py
────────────────────────────
Reusable KPI card components.
Renders styled metric tiles outside of st.metric
when more control over colour / layout is needed.
"""

import streamlit as st

# Five colour themes — one per card slot
_GRADIENTS = [
    ("linear-gradient(135deg,#0f2540,#1a3a5c)", "#2a5a8c"),  # Blue
    ("linear-gradient(135deg,#0f2d1a,#1a4a2e)", "#2a6e42"),  # Green
    ("linear-gradient(135deg,#2b1d00,#3d2a00)", "#7a5500"),  # Amber
    ("linear-gradient(135deg,#2d0f0f,#4a1a1a)", "#8c2a2a"),  # Red
    ("linear-gradient(135deg,#1a0f2d,#2a1a4a)", "#5a2a8c"),  # Purple
]


def kpi_card(
    slot: int,
    icon: str,
    label: str,
    value: str,
    delta: str = "",
    delta_positive: bool = True,
) -> str:
    """
    Return HTML for a single KPI card.

    Args:
        slot:           0–4, controls the gradient theme
        icon:           Emoji or text icon
        label:          Card title
        value:          Main metric value (pre-formatted string)
        delta:          Optional sub-label (e.g. "↑ 12.3%")
        delta_positive: If False, renders delta in red instead of green
    """
    grad, border = _GRADIENTS[slot % 5]
    delta_colour = "#3fb950" if delta_positive else "#ff7b72"
    delta_html   = (
        f'<div style="font-size:11px;color:{delta_colour};margin-top:4px;">{delta}</div>'
        if delta else ""
    )
    return f"""
    <div style="
        background:{grad};
        border:1px solid {border};
        border-radius:12px;
        padding:18px 20px;
        box-shadow:0 2px 8px rgba(0,0,0,0.4);
        height:100%;
    ">
        <div style="font-size:11px;color:#8b949e;font-weight:500;
                    letter-spacing:0.4px;margin-bottom:6px;">
            {icon} {label}
        </div>
        <div style="font-size:26px;font-weight:700;color:#ffffff;">
            {value}
        </div>
        {delta_html}
    </div>
    """


def render_kpi_row(cards: list[dict]) -> None:
    """
    Render up to 5 KPI cards in a single st.columns row.

    Args:
        cards: List of dicts with keys:
               icon, label, value, delta (opt), delta_positive (opt)
    """
    cols = st.columns(len(cards))
    for i, (col, card) in enumerate(zip(cols, cards)):
        html = kpi_card(
            slot=i,
            icon=card.get("icon", ""),
            label=card.get("label", ""),
            value=card.get("value", "—"),
            delta=card.get("delta", ""),
            delta_positive=card.get("delta_positive", True),
        )
        with col:
            st.markdown(html, unsafe_allow_html=True)
