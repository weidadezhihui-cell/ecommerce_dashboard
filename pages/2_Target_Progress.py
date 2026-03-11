"""
Target Progress — Half-circle speedometer gauges (arc up, right = goal).
Each metric (Sales, Net Profit) is in its own vertical column with Input,
Chart, and Summary inside a bordered card. Net Profit uses Total COGS from
Product Name Mapping on the main app.
"""

from __future__ import annotations

import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import to_money

# Card headers (dark teal)
TEAL_HEADER = "#137D78"
# Gauge gradient: match KPI page (#0f766e) for identical teal
TEAL = "#0f766e"
TEAL_KPI = "#0f766e"
RETURN_RATE_OVER_TARGET_RED = "#D32F2F"
LIGHT_GREY = "#E0E0E0"
LIGHT_TEAL = "#80CBC4"
LIGHT_RED = "#EF9A9A"


def _lerp_hex(c1: str, c2: str, t: float) -> str:
    """Interpolate between two hex colors; t in [0, 1]."""
    t = max(0, min(1, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def bucket_mask(txn: pd.Series, bucket: str) -> pd.Series:
    t = txn.astype(str)
    if bucket == "Order":
        return t.str.contains("order", case=False, na=False)
    if bucket == "Refund":
        return t.str.contains("refund", case=False, na=False)
    return pd.Series(True, index=txn.index)


def transfer_mask(df: pd.DataFrame) -> pd.Series:
    txn_series = df.get("txn_type", pd.Series([""] * len(df), index=df.index)).astype(str)
    if "type" in df.columns:
        fallback = df["type"].astype(str)
        txn_series = txn_series.where(txn_series.str.strip() != "", fallback)
    return txn_series.str.contains("transfer", case=False, na=False)


def safe_num(s: pd.Series) -> pd.Series:
    return to_money(s)


def compute_kpis(df_scope: pd.DataFrame) -> dict:
    df = df_scope.copy()
    for col in ["txn_type", "quantity", "product_sales", "total"]:
        if col not in df.columns:
            df[col] = 0 if col != "txn_type" else ""
    df["quantity"] = safe_num(df["quantity"])
    df["product_sales"] = safe_num(df["product_sales"])
    df["total"] = safe_num(df["total"])
    m_order = bucket_mask(df["txn_type"], "Order")
    m_refund = bucket_mask(df["txn_type"], "Refund")
    m_transfer = transfer_mask(df)
    units_sold = float(df.loc[m_order, "quantity"].sum())
    units_returned = float(df.loc[m_refund, "quantity"].sum())
    sales_order = float(df.loc[m_order, "product_sales"].sum())
    sales_refund = float(df.loc[m_refund, "product_sales"].sum())
    return {
        "units_sold": units_sold,
        "units_returned": units_returned,
        "net_sales": sales_order - sales_refund,
        "net_proceeds": float(df.loc[~m_transfer, "total"].sum()),
    }


def _half_gauge(
    actual: float,
    goal: float,
    value_label: str,
    goal_label: str,
    progress_color: str = TEAL,
    height: int = 480,
    zero_label: str = "$0",
) -> tuple[go.Figure, dict]:
    """
    Half-circle speedometer as a thick arc (half rainbow). Left = 0%, right = 100% (goal).
    Progress = gradient from light to full color; rest = grey. Labels: $0 (left), value (center), Goal (right) on one baseline.
    """
    if goal <= 0:
        goal = 1.0
    progress = min(actual / goal, 1.0)
    n_arc = 80
    r_inner, r_outer = 0.62, 1.0  # thick band like a rainbow

    # Light start color for gradient (lighter -> current color at goal); match KPI teal
    if progress_color in (TEAL, TEAL_HEADER, TEAL_KPI):
        start_color = LIGHT_TEAL
    elif progress_color == RETURN_RATE_OVER_TARGET_RED:
        start_color = LIGHT_RED
    else:
        start_color = _lerp_hex(progress_color, "#ffffff", 0.5)

    def band_points(theta_start: float, theta_end: float) -> tuple[list[float], list[float]]:
        """Closed polygon for the arc band from theta_start to theta_end (outer then inner reverse)."""
        xs, ys = [], []
        for i in range(n_arc + 1):
            t = i / n_arc
            th = theta_start + t * (theta_end - theta_start)
            xs.append(r_outer * math.cos(th))
            ys.append(r_outer * math.sin(th))
        for i in range(n_arc + 1):
            t = i / n_arc
            th = theta_end + t * (theta_start - theta_end)
            xs.append(r_inner * math.cos(th))
            ys.append(r_inner * math.sin(th))
        return xs, ys

    fig = go.Figure()

    # 1) Full half-rainbow band (grey background)
    x_bg, y_bg = band_points(math.pi, 0)
    fig.add_trace(
        go.Scatter(
            x=x_bg,
            y=y_bg,
            mode="lines",
            fill="toself",
            fillcolor=LIGHT_GREY,
            line=dict(color="#b0b0b0", width=1.5),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # 2) Progress segment as gradient (light at start -> full color toward goal); overlap slightly to avoid white lines
    n_seg = 24
    if progress > 0.001:
        theta_full_end = math.pi * (1 - progress)
        span = theta_full_end - math.pi
        overlap = 0.008 * span  # small overlap so no visible gap between segments
        for i in range(n_seg):
            t0 = i / n_seg
            t1 = (i + 1) / n_seg
            theta_a = math.pi + t0 * span
            theta_b = math.pi + t1 * span + (overlap if t1 < 1 else 0)
            theta_b = min(theta_b, theta_full_end)
            seg_color = _lerp_hex(start_color, progress_color, (i + 0.5) / n_seg)
            x_fill, y_fill = band_points(theta_a, theta_b)
            fig.add_trace(
                go.Scatter(
                    x=x_fill,
                    y=y_fill,
                    mode="lines",
                    fill="toself",
                    fillcolor=seg_color,
                    line=dict(color=seg_color, width=0),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
        # One invisible trace for hover
        x_h, y_h = band_points(math.pi, theta_full_end)
        fig.add_trace(
            go.Scatter(
                x=x_h,
                y=y_h,
                mode="lines",
                fill="toself",
                fillcolor="rgba(0,0,0,0)",
                line=dict(width=0),
                showlegend=False,
                hovertemplate=f"<b>YTD</b>: {value_label}<extra></extra>",
            )
        )

    # Value (center): bottom of number aligned with chart bottom (y=0); color = title background
    label_color = "#1f2937"
    annotations = [
        dict(
            text=f"<b>{value_label}</b>",
            x=0,
            y=0,
            xref="x",
            yref="y",
            yanchor="bottom",
            xanchor="center",
            showarrow=False,
            font=dict(size=48, color=TEAL_HEADER, family="Source Sans 3"),
            align="center",
        ),
        dict(
            text=f"<b>{zero_label}</b>",
            x=-1,
            y=-0.11,
            xref="x",
            yref="y",
            yanchor="top",
            xanchor="center",
            showarrow=False,
            font=dict(size=34, color=label_color, family="Source Sans 3"),
            align="center",
        ),
        dict(
            text=f"<b>Goal: {goal_label}</b>",
            x=1,
            y=-0.11,
            xref="x",
            yref="y",
            yanchor="top",
            xanchor="right",
            showarrow=False,
            font=dict(size=34, color=label_color, family="Source Sans 3"),
            align="right",
        ),
    ]

    fig_height = int(height * 1.10)
    # Match figure width to plot aspect (x range 3, y range 1.35) so chart fills width and aligns with gray bar
    plot_height_px = fig_height - 48  # minus top/bottom margins
    fig_width = int(plot_height_px * (3.0 / 1.35))
    fig.update_layout(
        xaxis=dict(visible=False, range=[-1.5, 1.5], scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False, range=[-0.2, 1.15]),
        margin=dict(t=24, b=24, l=0, r=0),
        width=fig_width,
        height=fig_height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        annotations=annotations,
        font=dict(size=1),
    )
    fig.update_layout(dragmode=False)
    config = {"displayModeBar": False, "displaylogo": False, "staticPlot": True}
    return fig, config


def _total_cogs_from_session(df_ytd: pd.DataFrame) -> float:
    """Total COGS from main app Product Name Mapping (sku_cogs_map)."""
    cogs_map = getattr(st.session_state, "sku_cogs_map", None) or {}
    if not cogs_map or "sku" not in df_ytd.columns:
        return 0.0
    m_order = bucket_mask(df_ytd["txn_type"], "Order")
    df_orders = df_ytd.loc[m_order] if "txn_type" in df_ytd.columns else df_ytd
    if "quantity" not in df_orders.columns:
        return 0.0
    total = 0.0
    for sku, grp in df_orders.groupby(df_orders["sku"].astype(str).str.strip()):
        if not sku or str(sku).lower() in ("nan", ""):
            continue
        units = float(grp["quantity"].sum())
        cogs_unit = float(cogs_map.get(sku, 0) or 0)
        total += units * cogs_unit
    return total


def _render_summary(actual: float, goal: float, value_label: str, metric_name: str) -> str:
    """Match second page: 'Currently at [X]% of annual target. Goal reached.' or remaining to hit goal."""
    if goal <= 0:
        return f"<div class='summary-text'>Currently at <b>{value_label}</b> (no target set).</div>"
    pct_of_target = (actual / goal) * 100
    if actual >= goal:
        return f"<div class='summary-text'>Currently at <b>100%</b> of annual target. Goal reached.</div>"
    remaining = goal - actual
    return f"<div class='summary-text'>Currently at <b>{pct_of_target:.0f}%</b> of annual target. <b>${remaining:,.0f}</b> remaining to hit goal.</div>"


def _days_passed_remaining(max_date: pd.Timestamp, ref_year: int) -> tuple[int, int]:
    """Return (days_passed_in_year, days_remaining_in_year)."""
    ytd_start = pd.Timestamp(year=ref_year, month=1, day=1)
    end_of_year = pd.Timestamp(year=ref_year, month=12, day=31)
    days_passed = max(1, (max_date - ytd_start).days + 1)
    days_remaining = max(0, (end_of_year - max_date).days)
    return days_passed, days_remaining


def _parse_dollar_text(raw: str) -> float:
    """Parse a string like '700,000' or '700000' to float."""
    if not raw or not raw.strip():
        return 0.0
    try:
        return float(str(raw).replace(",", "").strip())
    except ValueError:
        return 0.0


def _on_sales_goal_change():
    if "tp_sales_goal" in st.session_state:
        st.session_state.target_annual_sales_goal = float(st.session_state.tp_sales_goal)


def _on_sales_text_change():
    if "tp_sales_goal_text" in st.session_state:
        parsed = _parse_dollar_text(st.session_state.tp_sales_goal_text)
        parsed = max(0.0, parsed)
        st.session_state.target_annual_sales_goal = parsed
        st.session_state.tp_sales_goal = parsed
        # Do not set tp_sales_goal_text here (widget key); it is synced at start of script


def _on_profit_goal_change():
    if "tp_profit_goal" in st.session_state:
        st.session_state.target_annual_net_profit_goal = float(st.session_state.tp_profit_goal)


def _on_profit_text_change():
    if "tp_profit_goal_text" in st.session_state:
        parsed = _parse_dollar_text(st.session_state.tp_profit_goal_text)
        parsed = max(0.0, parsed)
        st.session_state.target_annual_net_profit_goal = parsed
        st.session_state.tp_profit_goal = parsed
        # Do not set tp_profit_goal_text here (widget key); it is synced at start of script


def _sparkline_bar(labels: list[str], values: list[float], bar_color: str = TEAL, height: int = 120) -> tuple[go.Figure, dict]:
    """Simple Plotly bar chart for last 6 months; values can be dollars or pct."""
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=bar_color))
    fig.update_layout(
        margin=dict(t=8, b=24, l=32, r=8),
        height=height,
        xaxis=dict(tickfont=dict(size=10), showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#eee", tickfont=dict(size=10)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    fig.update_layout(dragmode=False)
    config = {"displayModeBar": False, "displaylogo": False, "staticPlot": True}
    return fig, config


# --------------- Page ---------------
st.set_page_config(page_title="Target Progress", layout="wide")

st.markdown("""
    <style>
    /* Single font for all text and numbers (match Target Progress title) */
    :root { --target-font: "Source Sans 3", "Source Sans Pro", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .target-title, .target-intro,
    .target-title *, .target-intro *,
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header),
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) *,
    .summary-text, .summary-text *,
    .target-card-header, .target-card-header *,
    .target-footer-wrap, .target-footer-wrap *,
    .target-settings-section, .target-settings-section * {
        font-family: var(--target-font) !important;
        font-variant-numeric: normal !important;
    }
    .target-title { font-size: 2.75rem !important; font-weight: 700; color: #1f2937; margin-bottom: 0.5rem; }
    .target-intro { font-size: 1.75rem !important; color: #374151; margin-bottom: 2.5rem; }
    /* Premium card: two vertical columns, each one styled container */
    .target-progress-card {
        border: 1px solid #e6e9ef;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        background: #ffffff;
        overflow: hidden;
        margin-bottom: 1.5rem;
    }
    /* Wider space between the two goal cards */
    div[data-testid="stHorizontalBlock"]:has(> div:has(.target-card-header)) {
        gap: 8rem !important;
    }
    /* Card look: column that contains the teal card header */
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) {
        border: 1px solid #e6e9ef !important;
        border-radius: 12px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.12), 0 4px 12px rgba(0,0,0,0.08) !important;
        background: #ffffff !important;
        overflow: hidden !important;
        padding: 0 !important;
    }
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) > div {
        background: #ffffff !important;
    }
    /* Input area: goal input – match KPI "Select Year" style (light grey, bordered) */
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) > [data-testid="stTextInput"] {
        background-color: transparent !important;
        padding: 1rem 1.25rem 2.5rem 1.25rem !important;
        margin-bottom: 0 !important;
        margin-top: 0 !important;
    }
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) > [data-testid="stTextInput"] > div {
        background-color: transparent !important;
        border: none !important;
    }
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) [data-testid="stTextInput"] {
        border: none !important;
    }
    /* Much more space between filter and teal title section */
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) > [data-testid="stMarkdown"]:has(.target-card-header) {
        margin: 0 !important;
        padding: 0 !important;
        margin-top: 3.5rem !important;
    }
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) .target-card-header {
        margin: 0 !important;
    }
    /* Goal input label – match KPI Select Year: dark grey, slightly larger */
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) [data-testid="stTextInput"] label,
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) [data-testid="stTextInput"] label p {
        font-size: 1.7rem !important;
        font-weight: 400 !important;
        color: #31333f !important;
    }
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) [data-testid="stTextInput"] input {
        font-size: 2.2rem !important;
        font-family: var(--target-font) !important;
        font-variant-numeric: normal !important;
        height: 4.25rem !important;
        line-height: 1.2 !important;
        padding: 0.5rem 0.75rem !important;
        background-color: #f0f2f6 !important;
        border: none !important;
        border-radius: 0 !important;
        text-align: left !important;
        box-sizing: border-box !important;
        overflow: visible !important;
    }
    /* Main input container – same as KPI Select Year: light grey, thin border, 8px radius */
    div[data-testid="stHorizontalBlock"] > div:has(.target-card-header) [data-testid="stTextInput"] > div {
        background-color: #f0f2f6 !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: 8px !important;
        box-sizing: border-box !important;
        box-shadow: none !important;
        min-height: 4.25rem !important;
        overflow: visible !important;
        display: flex !important;
        align-items: center !important;
        padding: 0.35rem !important;
    }
    /* Target Settings section (legacy: when inputs were separate) */
    .target-settings-section {
        border: none !important;
        border-radius: 0;
        padding: 0.85rem 0.6rem 0.85rem 0.6rem;
        margin-bottom: 1rem;
        margin-top: 0.25rem;
        background-color: #ffffff;
        box-shadow: none !important;
    }
    /* Columns and inputs inside Target Settings (also target same vertical block if DOM nests differently) */
    .target-settings-section [data-testid="stHorizontalBlock"],
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stHorizontalBlock"] {
        gap: 0.5rem !important;
    }
    .target-settings-section [data-testid="stHorizontalBlock"] > div,
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stHorizontalBlock"] > div {
        min-height: 0 !important;
        padding: 0 4px 5px 4px !important;
        margin-bottom: 0 !important;
        border: none !important;
        box-shadow: none !important;
    }
    .target-settings-section [data-testid="stTextInput"] label,
    .target-settings-section [data-testid="stTextInput"] label p,
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stTextInput"] label,
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stTextInput"] label p {
        font-size: 1.9rem !important;
        font-weight: 400 !important;
        color: #6b7280 !important;
    }
    /* Hide "Press Enter to apply" – hide completely or make blank */
    .target-settings-section [data-testid="stInputInstructions"],
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stInputInstructions"],
    .target-settings-section [data-testid="stTextInput"] [data-testid="stInputInstructions"],
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stTextInput"] [data-testid="stInputInstructions"],
    .target-settings-section [data-testid="stTextInput"] small,
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stTextInput"] small {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        overflow: hidden !important;
        opacity: 0 !important;
        font-size: 0 !important;
        line-height: 0 !important;
        color: transparent !important;
        position: absolute !important;
        left: -9999px !important;
        pointer-events: none !important;
    }
    .target-settings-section [data-testid="stTextInput"] input,
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stTextInput"] input {
        font-size: 2.2rem !important;
        font-family: var(--target-font) !important;
        font-variant-numeric: normal !important;
        font-weight: 400 !important;
        height: 5.5rem !important;
        line-height: 5.5rem !important;
        padding: 0 1.25rem !important;
        color: #111 !important;
        width: 100% !important;
        box-sizing: border-box !important;
        min-width: 0 !important;
        border: none !important;
        border-radius: 8px !important;
        box-shadow: none !important;
        outline: none !important;
        background-color: #f0f2f6 !important;
        text-align: left !important;
        position: relative !important;
        z-index: 1 !important;
    }
    .target-settings-section [data-testid="stTextInput"] input:focus,
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stTextInput"] input:focus {
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }
    .target-settings-section [data-testid="stTextInput"] > div,
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stTextInput"] > div {
        width: 100% !important;
        max-width: 100% !important;
        display: flex !important;
        align-items: center !important;
        border: none !important;
        box-shadow: none !important;
        background-color: #f0f2f6 !important;
        border-radius: 8px !important;
        position: relative !important;
        z-index: 1 !important;
    }
    .target-settings-section [data-testid="stCaptionContainer"],
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stCaptionContainer"] {
        font-size: 1.5rem !important;
        margin: 6px 0 0 0 !important;
        padding: 0 !important;
        color: #374151 !important;
    }
    .target-settings-section [data-testid="stTextInput"],
    div[data-testid="stVerticalBlock"]:has(.target-settings-section) [data-testid="stTextInput"] {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }
    /* Columns that contain text inputs (elsewhere): no card look */
    div[data-testid="stHorizontalBlock"]:has([data-testid="stTextInput"]) > div {
        min-height: 0 !important;
        padding: 0 8px 5px 8px !important;
        margin-bottom: 0 !important;
        border: none !important;
        box-shadow: none !important;
    }
    /* Header: match KPI page – dark teal, bold white; zero gap so it touches card edges */
    .target-card-header {
        background: #0f766e;
        color: #fff;
        padding: 1rem 1.25rem;
        text-align: center;
        border-radius: 0;
        margin: 0 !important;
        font-size: 42px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .target-card-header .target-card-subtitle {
        display: inline-block;
        font-size: 32px;
        font-weight: 700;
        margin-top: 6px;
        margin-bottom: 0;
        padding-bottom: 6px;
        border-bottom: 4px solid rgba(255, 255, 255, 0.9);
        opacity: 0.95;
        text-transform: none;
        letter-spacing: normal;
    }
    div[data-testid="stHorizontalBlock"] > div [data-testid="stPlotlyChart"] { margin-top: -6px; margin-bottom: -8px; padding: 0 1rem; text-align: center; }
    div[data-testid="stHorizontalBlock"] > div [data-testid="stPlotlyChart"]:first-of-type { margin-top: -8px; margin-bottom: -8px; }
    .summary-text {
        text-align: center;
        font-size: 2rem !important;
        font-weight: 400;
        color: #374151;
        margin-top: 1.25rem;
        padding: 0 1rem 0.75rem 1rem;
    }
    .forecast-separator { border: none; margin: 0; padding: 0; height: 0; }
    .target-footer-wrap {
        border-top: 1px solid #e6e9ef;
        padding: 1rem 1.25rem 1.25rem;
        background: #fafbfc;
    }
    .target-footer-row { display: flex; align-items: center; gap: 0.75rem; padding: 0.6rem 0; font-size: 1.6rem; color: #374151; }
    .target-footer-row .target-footer-icon { opacity: 0.85; font-size: 1.6rem; }
    .target-footer-row .target-footer-label { font-weight: 700 !important; min-width: 10rem; font-size: 1.6rem; }
    .target-footer-row .target-footer-value { font-weight: 700; color: #1f2937; font-size: 1.6rem; }
    .target-footer-status-done { color: #0f766e; font-weight: 700; font-size: 1.6rem; }
    .target-footer-status-icon-done { color: #16a34a; font-size: 1.6rem; }
    /* Hide 'Press Enter to apply' everywhere so readers don't see it */
    div[data-testid="InputInstructions"],
    div[data-testid="stInputInstructions"],
    [data-testid*="InputInstructions"],
    [data-testid*="InputInstruction"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        overflow: hidden !important;
        opacity: 0 !important;
        position: absolute !important;
        left: -9999px !important;
        pointer-events: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 class='target-title'>Target Progress</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='target-intro'>Track performance against your annual goals. Set your targets below to monitor progress for the current year.</p>",
    unsafe_allow_html=True,
)

if "df_processed" not in st.session_state or st.session_state.df_processed is None:
    st.info("Upload data on the main page first.")
    st.stop()

df_base = st.session_state.df_processed.copy()
if "date" not in df_base.columns:
    st.warning("Processed data has no date column.")
    st.stop()
df_base["date"] = pd.to_datetime(df_base["date"], errors="coerce")
df_base = df_base.dropna(subset=["date"])
if df_base.empty:
    st.warning("No valid dates.")
    st.stop()

max_date = df_base["date"].max()
ref_year = max_date.year
ytd_start = pd.Timestamp(year=ref_year, month=1, day=1)
df_ytd = df_base[(df_base["date"] >= ytd_start) & (df_base["date"] <= max_date)]
kpis = compute_kpis(df_ytd)

ytd_sales = float(kpis["net_sales"])
ytd_net_proceeds = float(kpis["net_proceeds"])
ytd_units_sold = kpis["units_sold"]
ytd_units_returned = kpis["units_returned"]
ytd_return_rate_pct = (ytd_units_returned / ytd_units_sold * 100) if ytd_units_sold else 0.0

if "target_annual_sales_goal" not in st.session_state:
    st.session_state.target_annual_sales_goal = 100_000.0
if "target_annual_net_profit_goal" not in st.session_state:
    st.session_state.target_annual_net_profit_goal = 20_000.0
# Sync widget keys from target_* for inputs; text inputs for Sales/Profit show comma-formatted values
if "tp_sales_goal" not in st.session_state:
    st.session_state.tp_sales_goal = float(st.session_state.target_annual_sales_goal)
if "tp_profit_goal" not in st.session_state:
    st.session_state.tp_profit_goal = float(st.session_state.target_annual_net_profit_goal)
# Always set display text from numeric goal (before widgets run) so we never modify widget keys after instantiation
st.session_state.tp_sales_goal_text = f"{st.session_state.target_annual_sales_goal:,.0f}"
st.session_state.tp_profit_goal_text = f"{st.session_state.target_annual_net_profit_goal:,.0f}"

total_cogs = _total_cogs_from_session(df_ytd)
ytd_net_profit = ytd_net_proceeds - total_cogs
date_str = f"Jan 1 – {max_date.strftime('%b %d')}, {ref_year}"

days_passed, days_remaining = _days_passed_remaining(max_date, ref_year)
dec_str = f"Dec 31st, {ref_year}"
sales_goal = float(st.session_state.target_annual_sales_goal)
profit_goal = float(st.session_state.target_annual_net_profit_goal)
year_days = 365

# --------------- Two cards: Sales (col1) and Net Profit (col2) ---------------
ytd_label = f"Year to Date ({date_str})"
col1, col2 = st.columns(2)

with col1:
    with st.container():
        st.text_input(
            "Annual Sales Goal ($)",
            value=st.session_state.tp_sales_goal_text,
            key="tp_sales_goal_text",
            on_change=_on_sales_text_change,
            placeholder="e.g. 10,000,000",
        )
        st.markdown(
            f'<div class="target-card-header">TOTAL SALES<br><span class="target-card-subtitle">{ytd_label}</span></div>',
            unsafe_allow_html=True,
        )
        fig1, cfg1 = _half_gauge(
            ytd_sales, sales_goal, f"${ytd_sales:,.0f}", f"${sales_goal:,.0f}",
            progress_color=TEAL_KPI,
        )
        st.plotly_chart(fig1, use_container_width=True, key="tp_sales", config=cfg1)
        st.markdown(_render_summary(ytd_sales, sales_goal, f"${ytd_sales:,.0f}", "sales"), unsafe_allow_html=True)
        st.markdown('<hr class="forecast-separator" />', unsafe_allow_html=True)
        proj_sales = (ytd_sales / days_passed) * year_days if days_passed else 0
        req_sales_per_day = (sales_goal - ytd_sales) / max(days_remaining, 1) if (days_remaining and ytd_sales < sales_goal) else 0
        sales_status = "Goal reached" if ytd_sales >= sales_goal else "In progress"
        sales_status_icon = '<span class="target-footer-status-icon-done">✔</span>' if ytd_sales >= sales_goal else "—"
        sales_req_display = f"${req_sales_per_day:,.0f}/day" if ytd_sales < sales_goal else "–"
        sales_status_html = f'<span class="target-footer-status-done">{sales_status}</span>' if ytd_sales >= sales_goal else f'<span>{sales_status}</span>'
        st.markdown(
            f'<div class="target-footer-wrap">'
            f'<div class="target-footer-row"><span class="target-footer-icon">📋</span><span class="target-footer-label">On track for:</span> <span class="target-footer-value">${proj_sales:,.0f}</span> by {dec_str}</div>'
            f'<div class="target-footer-row"><span class="target-footer-icon">📅</span><span class="target-footer-label">Required per day:</span> <span>{sales_req_display}</span></div>'
            f'<div class="target-footer-row"><span class="target-footer-icon">{sales_status_icon}</span><span class="target-footer-label">Status:</span> {sales_status_html}</div>'
            f'</div>',
        unsafe_allow_html=True,
        )

with col2:
    with st.container():
        st.text_input(
            "Annual Net Profit Goal ($)",
            value=st.session_state.tp_profit_goal_text,
            key="tp_profit_goal_text",
            on_change=_on_profit_text_change,
            placeholder="e.g. 20,000",
        )
        st.markdown(
            f'<div class="target-card-header">TOTAL NET PROFIT<br><span class="target-card-subtitle">{ytd_label}</span></div>',
            unsafe_allow_html=True,
        )
        fig2, cfg2 = _half_gauge(
            ytd_net_profit, profit_goal, f"${ytd_net_profit:,.0f}", f"${profit_goal:,.0f}",
            progress_color=TEAL_KPI,
        )
        st.plotly_chart(fig2, use_container_width=True, key="tp_profit", config=cfg2)
        st.markdown(_render_summary(ytd_net_profit, profit_goal, f"${ytd_net_profit:,.0f}", "net profit"), unsafe_allow_html=True)
        st.markdown('<hr class="forecast-separator" />', unsafe_allow_html=True)
        proj_profit = (ytd_net_profit / days_passed) * year_days if days_passed else 0
        req_profit_per_day = (profit_goal - ytd_net_profit) / max(days_remaining, 1) if (days_remaining and ytd_net_profit < profit_goal) else 0
        profit_status = "Goal reached" if ytd_net_profit >= profit_goal else "In progress"
        profit_status_icon = '<span class="target-footer-status-icon-done">✔</span>' if ytd_net_profit >= profit_goal else "—"
        profit_req_display = f"${req_profit_per_day:,.0f}/day" if ytd_net_profit < profit_goal else "–"
        profit_status_html = f'<span class="target-footer-status-done">{profit_status}</span>' if ytd_net_profit >= profit_goal else f'<span>{profit_status}</span>'
        st.markdown(
            f'<div class="target-footer-wrap">'
            f'<div class="target-footer-row"><span class="target-footer-icon">📋</span><span class="target-footer-label">On track for:</span> <span class="target-footer-value">${proj_profit:,.0f}</span> by {dec_str}</div>'
            f'<div class="target-footer-row"><span class="target-footer-icon">📅</span><span class="target-footer-label">Required per day:</span> <span>{profit_req_display}</span></div>'
            f'<div class="target-footer-row"><span class="target-footer-icon">{profit_status_icon}</span><span class="target-footer-label">Status:</span> {profit_status_html}</div>'
            f'</div>',
        unsafe_allow_html=True,
        )
