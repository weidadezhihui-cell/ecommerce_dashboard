"""
Target Progress — Half-circle speedometer gauges (arc up, right = goal).
Each metric (Sales, Return Rate, Net Profit) is in its own vertical column
with Input, Chart, and Summary inside a bordered card. Net Profit uses Total
COGS from Product Name Mapping on the main app.
"""

from __future__ import annotations

import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import to_money

TEAL = "#008080"
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
    Progress = gradient from light to full color; rest = grey. If actual >= goal, full arc colored.
    """
    if goal <= 0:
        goal = 1.0
    progress = min(actual / goal, 1.0)
    n_arc = 80
    r_inner, r_outer = 0.62, 1.0  # thick band like a rainbow

    # Light start color for gradient (lighter -> current color at goal)
    if progress_color == TEAL:
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

    # Annotations: YTD value inside/below arc; zero at left end; goal beneath the right end of the arc
    annotations = [
        dict(
            text=f"<b>{value_label}</b>",
            x=0,
            y=0.15,
            xref="x",
            yref="y",
            yanchor="middle",
            xanchor="center",
            showarrow=False,
            font=dict(size=18, color=progress_color, family="Inter"),
            align="center",
        ),
        dict(
            text=f"<b>{zero_label}</b>",
            x=-1,
            y=-0.14,
            xref="x",
            yref="y",
            yanchor="top",
            xanchor="center",
            showarrow=False,
            font=dict(size=16, color="#333", family="Inter"),
            align="center",
        ),
        dict(
            text=f"<b>{goal_label}</b>",
            x=0.88,
            y=-0.14,
            xref="x",
            yref="y",
            yanchor="top",
            xanchor="center",
            showarrow=False,
            font=dict(size=16, color="#333", family="Inter"),
            align="center",
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
    if goal <= 0:
        return f"<div class='summary-text'>The year to date {metric_name} is <b>{value_label}</b>.</div>"
    pct = (actual - goal) / goal * 100
    status = "above" if pct >= 0 else "below"
    return f"<div class='summary-text'>The year to date {metric_name} is <b>{value_label}</b>, and is <b>{abs(pct):.0f}% {status}</b> goal.</div>"


def _days_passed_remaining(max_date: pd.Timestamp, ref_year: int) -> tuple[int, int]:
    """Return (days_passed_in_year, days_remaining_in_year)."""
    ytd_start = pd.Timestamp(year=ref_year, month=1, day=1)
    end_of_year = pd.Timestamp(year=ref_year, month=12, day=31)
    days_passed = max(1, (max_date - ytd_start).days + 1)
    days_remaining = max(0, (end_of_year - max_date).days)
    return days_passed, days_remaining


def _last_6_months_series(
    df_base: pd.DataFrame,
    max_date: pd.Timestamp,
    cogs_fn: callable,
) -> tuple[list[str], list[float], list[float], list[float]]:
    """
    Return (month_labels, sales_list, net_profit_list, return_rate_pct_list) for the last 6 calendar months.
    """
    month_starts = pd.date_range(end=max_date.replace(day=1), periods=6, freq="MS")
    labels = [d.strftime("%b %y") for d in month_starts]
    sales_list, profit_list, return_list = [], [], []
    for ms in month_starts:
        me = ms + pd.DateOffset(months=1)
        df_m = df_base[(df_base["date"] >= ms) & (df_base["date"] < me)]
        k = compute_kpis(df_m)
        sales_list.append(float(k["net_sales"]))
        cogs = cogs_fn(df_m)
        profit_list.append(float(k["net_proceeds"]) - cogs)
        u_sold, u_ret = k["units_sold"], k["units_returned"]
        return_list.append((u_ret / u_sold * 100) if u_sold else 0.0)
    return labels, sales_list, profit_list, return_list


def _year_chart_series_with_forecast(
    df_base: pd.DataFrame,
    max_date: pd.Timestamp,
    ref_year: int,
    cogs_fn: callable,
    ytd_sales: float,
    ytd_net_profit: float,
    ytd_return_rate_pct: float,
) -> tuple[list[str], list[float], list[float], list[float], int]:
    """
    Return (labels, sales, profit, return_rate_pct, n_historical) for the chart:
    last 6 calendar months (historical) + remaining months in ref_year (forecast).
    Forecast values: monthly average from YTD for sales/profit; YTD return rate for return rate.
    """
    month_starts = pd.date_range(end=max_date.replace(day=1), periods=6, freq="MS")
    labels = [d.strftime("%b %y") for d in month_starts]
    sales_list, profit_list, return_list = [], [], []
    for ms in month_starts:
        me = ms + pd.DateOffset(months=1)
        df_m = df_base[(df_base["date"] >= ms) & (df_base["date"] < me)]
        k = compute_kpis(df_m)
        sales_list.append(float(k["net_sales"]))
        cogs = cogs_fn(df_m)
        profit_list.append(float(k["net_proceeds"]) - cogs)
        u_sold, u_ret = k["units_sold"], k["units_returned"]
        return_list.append((u_ret / u_sold * 100) if u_sold else 0.0)
    n_historical = len(labels)
    num_months_ytd = max(1, max_date.month)
    avg_sales = ytd_sales / num_months_ytd
    avg_profit = ytd_net_profit / num_months_ytd
    for m in range(max_date.month + 1, 13):
        month_start = pd.Timestamp(year=ref_year, month=m, day=1)
        labels.append(month_start.strftime("%b %y"))
        sales_list.append(avg_sales)
        profit_list.append(avg_profit)
        return_list.append(ytd_return_rate_pct)
    return labels, sales_list, profit_list, return_list, n_historical


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


def _on_return_target_change():
    if "tp_return_target" in st.session_state:
        st.session_state.target_max_return_rate_pct = float(st.session_state.tp_return_target)


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


def _sparkline_bar_with_forecast(
    labels: list[str],
    values: list[float],
    n_historical: int,
    height: int = 120,
) -> tuple[go.Figure, dict]:
    """Bar chart with historical months in TEAL and forecast months in LIGHT_TEAL."""
    colors = [TEAL] * n_historical + [LIGHT_TEAL] * (len(labels) - n_historical)
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=colors))
    fig.update_layout(
        margin=dict(t=6, b=20, l=32, r=8),
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
    .target-title { font-size: 2.75rem !important; font-weight: 700; color: #1f2937; margin-bottom: 0.5rem; }
    .target-intro { font-size: 1.2rem !important; color: #374151; margin-bottom: 1.25rem; }
    /* Style the three column containers as cards so input + content sit inside one box */
    div[data-testid="stHorizontalBlock"] > div {
        border: 2.5px solid #666666;
        border-radius: 12px;
        padding: 16px 20px;
        background-color: #ffffff;
        box-shadow: 0 20px 40px rgba(0,0,0,0.18), 0 10px 20px rgba(0,0,0,0.14);
        margin-bottom: 20px;
        min-height: 600px;
    }
    div[data-testid="stHorizontalBlock"] > div .chart-title { text-align: center; color: #666; font-size: 1.6875rem !important; margin-top: 0; margin-bottom: -48px; }
    div[data-testid="stHorizontalBlock"] > div [data-testid="stPlotlyChart"] { margin-top: -6px; margin-bottom: -8px; }
    div[data-testid="stHorizontalBlock"] > div [data-testid="stPlotlyChart"]:first-of-type { margin-top: -56px; margin-bottom: -8px; }
    .summary-text {
        text-align: center;
        font-size: 1.625rem !important;
        color: #374151;
        margin-top: -32px;
        padding-bottom: 24px;
    }
    .forecast-separator {
        border-top: 1px solid #d1d5db;
        margin: 64px 0 6px 0;
        width: 100%;
    }
    .forecast-section { margin-top: 2px; margin-bottom: 2px; }
    .diagnostic-label { font-size: 1.1rem !important; color: #374151; text-align: center; margin: 2px 0; }
    .goal-reached { font-size: 1.1rem !important; color: #008080; font-weight: 700; text-align: center; margin: 2px 0; }
    div[data-testid="stHorizontalBlock"] > div [data-testid="stNumberInput"] { margin-bottom: 2px; padding: 0; }
    [data-testid="stNumberInput"] label,
    [data-testid="stNumberInput"] label p,
    div[data-testid="stHorizontalBlock"] > div [data-testid="stNumberInput"] label,
    div[data-testid="stHorizontalBlock"] > div [data-testid="stNumberInput"] label p { font-size: 1.65rem !important; font-weight: 600 !important; }
    div[data-testid="stHorizontalBlock"] > div [data-testid="stNumberInput"] input { min-height: 2.75rem; font-size: 1.65rem !important; }
    div[data-testid="stHorizontalBlock"] > div [data-testid="stTextInput"] input { min-height: 2.75rem; font-size: 1.65rem !important; }
    div[data-testid="stHorizontalBlock"] > div [data-testid="stTextInput"] label,
    div[data-testid="stHorizontalBlock"] > div [data-testid="stTextInput"] label p { font-size: 1.65rem !important; font-weight: 600 !important; }
    .input-value-display { font-size: 1.35rem !important; font-weight: 600; color: #1f2937; margin: 2px 0 6px 0; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 class='target-title'>Target Progress</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='target-intro'>This page tracks your performance against annual goals. "
    "Please type in your annual targets for Total Sales, Net Profits, and Average Return Rate for the current year "
    "(defined as the most recent year in your data) to monitor progress.</p>",
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
if "target_max_return_rate_pct" not in st.session_state:
    st.session_state.target_max_return_rate_pct = 10.0
if "target_annual_net_profit_goal" not in st.session_state:
    st.session_state.target_annual_net_profit_goal = 20_000.0
# Sync widget keys from target_* for inputs; text inputs for Sales/Profit show comma-formatted values
if "tp_sales_goal" not in st.session_state:
    st.session_state.tp_sales_goal = float(st.session_state.target_annual_sales_goal)
if "tp_profit_goal" not in st.session_state:
    st.session_state.tp_profit_goal = float(st.session_state.target_annual_net_profit_goal)
if "tp_return_target" not in st.session_state:
    st.session_state.tp_return_target = float(st.session_state.target_max_return_rate_pct)
# Always set display text from numeric goal (before widgets run) so we never modify widget keys after instantiation
st.session_state.tp_sales_goal_text = f"{st.session_state.target_annual_sales_goal:,.0f}"
st.session_state.tp_profit_goal_text = f"{st.session_state.target_annual_net_profit_goal:,.0f}"

total_cogs = _total_cogs_from_session(df_ytd)
ytd_net_profit = ytd_net_proceeds - total_cogs
date_str = f"Jan 1 – {max_date.strftime('%b %d')}, {ref_year}"

days_passed, days_remaining = _days_passed_remaining(max_date, ref_year)
(
    chart_labels,
    chart_sales,
    chart_profit,
    chart_return_pct,
    n_historical,
) = _year_chart_series_with_forecast(
    df_base,
    max_date,
    ref_year,
    _total_cogs_from_session,
    ytd_sales,
    ytd_net_profit,
    ytd_return_rate_pct,
)
dec_str = f"Dec 31st, {ref_year}"

# --------------- 3 columns: Col1=Sales, Col2=Net Profit, Col3=Return Rate ---------------
col1, col2, col3 = st.columns(3)
year_days = 365

with col1:
    st.text_input(
        "Annual Sales Goal ($)",
        value=st.session_state.tp_sales_goal_text,
        key="tp_sales_goal_text",
        on_change=_on_sales_text_change,
    )
    sales_goal = float(st.session_state.target_annual_sales_goal)
    st.markdown(f'<p class="input-value-display">Goal: <b>${sales_goal:,.0f}</b></p>', unsafe_allow_html=True)
    st.markdown(f'<p class="chart-title"><b>Total Sales</b><br>{date_str}</p>', unsafe_allow_html=True)
    fig1, cfg1 = _half_gauge(ytd_sales, sales_goal, f"${ytd_sales:,.0f}", f"${sales_goal:,.0f}", progress_color=TEAL)
    st.plotly_chart(fig1, use_container_width=True, key="tp_sales", config=cfg1)
    st.markdown(_render_summary(ytd_sales, sales_goal, f"${ytd_sales:,.0f}", "sales"), unsafe_allow_html=True)
    st.markdown('<hr class="forecast-separator" />', unsafe_allow_html=True)
    st.markdown('<div class="forecast-section">', unsafe_allow_html=True)
    proj_sales = (ytd_sales / days_passed) * year_days if days_passed else 0
    st.markdown(f'<p class="diagnostic-label">On track for <b>${proj_sales:,.0f}</b> by {dec_str}.</p>', unsafe_allow_html=True)
    if ytd_sales >= sales_goal:
        st.markdown('<p class="goal-reached">🎉 Goal has been reached!</p>', unsafe_allow_html=True)
    else:
        req_sales_per_day = (sales_goal - ytd_sales) / max(days_remaining, 1) if days_remaining else 0
        st.markdown(f'<p class="diagnostic-label">Required: <b>${req_sales_per_day:,.0f}</b>/day to hit goal.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    sp1, sp_cfg = _sparkline_bar_with_forecast(chart_labels, chart_sales, n_historical, height=120)
    st.plotly_chart(sp1, use_container_width=True, key="tp_spark_sales", config=sp_cfg)

with col2:
    st.text_input(
        "Annual Net Profit Goal ($)",
        value=st.session_state.tp_profit_goal_text,
        key="tp_profit_goal_text",
        on_change=_on_profit_text_change,
    )
    profit_goal = float(st.session_state.target_annual_net_profit_goal)
    st.markdown(f'<p class="input-value-display">Goal: <b>${profit_goal:,.0f}</b></p>', unsafe_allow_html=True)
    st.markdown(f'<p class="chart-title"><b>Total Net Profit</b><br>{date_str}</p>', unsafe_allow_html=True)
    fig2, cfg2 = _half_gauge(ytd_net_profit, profit_goal, f"${ytd_net_profit:,.0f}", f"${profit_goal:,.0f}", progress_color=TEAL)
    st.plotly_chart(fig2, use_container_width=True, key="tp_profit", config=cfg2)
    st.markdown(_render_summary(ytd_net_profit, profit_goal, f"${ytd_net_profit:,.0f}", "net profit"), unsafe_allow_html=True)
    st.markdown('<hr class="forecast-separator" />', unsafe_allow_html=True)
    st.markdown('<div class="forecast-section">', unsafe_allow_html=True)
    proj_profit = (ytd_net_profit / days_passed) * year_days if days_passed else 0
    st.markdown(f'<p class="diagnostic-label">On track for <b>${proj_profit:,.0f}</b> by {dec_str}.</p>', unsafe_allow_html=True)
    if ytd_net_profit >= profit_goal:
        st.markdown('<p class="goal-reached">🎉 Goal has been reached!</p>', unsafe_allow_html=True)
    else:
        req_profit_per_day = (profit_goal - ytd_net_profit) / max(days_remaining, 1) if days_remaining else 0
        st.markdown(f'<p class="diagnostic-label">Required: <b>${req_profit_per_day:,.0f}</b>/day to hit goal.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    sp2, _ = _sparkline_bar_with_forecast(chart_labels, chart_profit, n_historical, height=120)
    st.plotly_chart(sp2, use_container_width=True, key="tp_spark_profit", config=sp_cfg)

with col3:
    st.number_input(
        "Max Return Rate Target (%)",
        min_value=0.0,
        max_value=100.0,
        step=0.5,
        key="tp_return_target",
        format="%.1f",
        on_change=_on_return_target_change,
    )
    _on_return_target_change()
    return_target = float(st.session_state.target_max_return_rate_pct)
    st.markdown(f'<p class="input-value-display">Target: <b>{return_target:,.1f}%</b></p>', unsafe_allow_html=True)
    st.markdown(f'<p class="chart-title"><b>Average Return Rate</b><br>{date_str}</p>', unsafe_allow_html=True)
    return_color = RETURN_RATE_OVER_TARGET_RED if ytd_return_rate_pct > return_target else TEAL
    ytd_return_str = f"{int(round(ytd_return_rate_pct))}%"
    return_goal_str = f"{int(round(return_target))}%"
    fig3, cfg3 = _half_gauge(ytd_return_rate_pct, return_target, ytd_return_str, return_goal_str, progress_color=return_color, zero_label="0%")
    st.plotly_chart(fig3, use_container_width=True, key="tp_return", config=cfg3)
    st.markdown(_render_summary(ytd_return_rate_pct, return_target, ytd_return_str, "return rate"), unsafe_allow_html=True)
    st.markdown('<hr class="forecast-separator" />', unsafe_allow_html=True)
    st.markdown('<div class="forecast-section">', unsafe_allow_html=True)
    st.markdown(f'<p class="diagnostic-label">On track for <b>{ytd_return_rate_pct:.1f}%</b> avg by {dec_str}.</p>', unsafe_allow_html=True)
    if ytd_return_rate_pct <= return_target:
        st.markdown('<p class="goal-reached">🎉 Goal has been reached!</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p class="diagnostic-label">Target: ≤<b>{return_goal_str}</b> through Dec 31.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    sp3, _ = _sparkline_bar_with_forecast(chart_labels, chart_return_pct, n_historical, height=120)
    st.plotly_chart(sp3, use_container_width=True, key="tp_spark_return", config=sp_cfg)
