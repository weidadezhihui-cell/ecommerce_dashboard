"""
Key Performance Indicator Page
High-level KPI overview: units, sales, net proceeds with year filter.
"""

from __future__ import annotations

import html
from datetime import date, timedelta
from typing import Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

from utils import to_money

TEAL = "#0f766e"


def _safe_float(val, default: float = 0.0) -> float:
    """Convert any value to float using pd.to_numeric(..., errors='coerce'); use default if invalid."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return default if pd.isna(val) else float(val)
    n = pd.to_numeric(val, errors="coerce")
    return default if pd.isna(n) else float(n)


def bucket_mask(txn: pd.Series, bucket: str) -> pd.Series:
    t = txn.astype(str)
    if bucket == "Order":
        return t.str.contains("order", case=False, na=False)
    if bucket == "Refund":
        return t.str.contains("refund", case=False, na=False)
    if bucket == "Liquidations":
        return t.str.contains("liquidation", case=False, na=False)
    if bucket == "Adjustment":
        return t.str.contains("adjustment", case=False, na=False)
    return pd.Series(True, index=txn.index)


def safe_num(s: pd.Series) -> pd.Series:
    return to_money(s)


def transfer_mask(df: pd.DataFrame) -> pd.Series:
    txn_series = df.get("txn_type", pd.Series([""] * len(df), index=df.index)).astype(str)
    if "type" in df.columns:
        fallback = df["type"].astype(str)
        txn_series = txn_series.where(txn_series.str.strip() != "", fallback)
    return txn_series.str.contains("transfer", case=False, na=False)


def compute_kpis(df_scope: pd.DataFrame) -> Dict:
    df = df_scope.copy()
    if "txn_type" not in df.columns:
        df["txn_type"] = ""
    if "quantity" not in df.columns:
        df["quantity"] = 0
    if "product_sales" not in df.columns:
        df["product_sales"] = 0
    if "total" not in df.columns:
        df["total"] = 0
    df["quantity"] = safe_num(df["quantity"])
    df["product_sales"] = safe_num(df["product_sales"])
    df["total"] = safe_num(df["total"])
    m_order = bucket_mask(df["txn_type"], "Order")
    m_refund = bucket_mask(df["txn_type"], "Refund")
    m_transfer = transfer_mask(df)
    units_sold = float(df.loc[m_order, "quantity"].sum())
    units_returned = float(df.loc[m_refund, "quantity"].sum())
    net_units = units_sold - units_returned
    sales_order = float(df.loc[m_order, "product_sales"].sum())
    sales_refund = float(df.loc[m_refund, "product_sales"].sum())
    net_sales = sales_order - sales_refund
    net_proceeds = float(df.loc[~m_transfer, "total"].sum())
    return {
        "units_sold": units_sold,
        "units_returned": units_returned,
        "net_units": net_units,
        "net_sales": net_sales,
        "net_proceeds": net_proceeds,
    }


def _fmt_money(x: float) -> str:
    x = _safe_float(x, 0.0)
    ax = abs(x)
    if ax >= 1e6:
        return f"${x/1e6:.1f}M"
    if ax >= 1e3:
        return f"${x/1e3:.1f}K"
    return f"${x:,.0f}"


def _fmt_units(x: float) -> str:
    x = _safe_float(x, 0.0)
    ax = abs(x)
    if ax >= 1e6:
        return f"{x/1e6:.1f}M"
    if ax >= 1e3:
        return f"{x/1e3:.1f}K"
    return f"{x:,.0f}"


def generate_summary(selected_years: List[int], df: pd.DataFrame) -> List[str]:
    required = ["Year", "Units Sold", "Units Returned", "Return Rate", "Sales", "Amazon Fees", "Net Proceeds"]
    if not all(c in df.columns for c in required):
        return []
    sub = df[df["Year"].isin(selected_years)].sort_values("Year")
    if sub.empty:
        return []
    out: List[str] = []
    if len(selected_years) == 1:
        r = sub.iloc[0]
        sales = _safe_float(r["Sales"], 0.0)
        units_sold = _safe_float(r["Units Sold"], 0.0)
        units_ret = _safe_float(r["Units Returned"], 0.0)
        rr = _safe_float(r["Return Rate"], 0.0)
        fees = _safe_float(r["Amazon Fees"], 0.0)
        net = _safe_float(r["Net Proceeds"], 0.0)
        fee_ratio = (fees / sales) if sales else 0.0
        net_margin = (net / sales) if sales else 0.0
        out.append(f"• Sales {_fmt_money(sales)} with {_fmt_units(units_sold)} units sold.")
        out.append(f"• Return rate {rr*100:.1f}% with {_fmt_units(units_ret)} units returned.")
        out.append(f"• Amazon fees {_fmt_money(fees)}; fee ratio (fees/sales) {fee_ratio*100:.1f}%.")
        out.append(f"• Net proceeds {_fmt_money(net)}; net margin (net/sales) {net_margin*100:.1f}%.")
        if fee_ratio > 0.60:
            out.append("• Watchlist: elevated fee ratio.")
        elif net_margin < 0.40:
            out.append("• Watchlist: margin compression risk.")
        else:
            out.append("• No major structural red flags.")
        return out
    earliest = int(sub["Year"].min())
    latest = int(sub["Year"].max())
    re = sub[sub["Year"] == earliest].iloc[0]
    rl = sub[sub["Year"] == latest].iloc[0]
    sales_e = _safe_float(re["Sales"], 0.0)
    sales_l = _safe_float(rl["Sales"], 0.0)
    units_e = _safe_float(re["Units Sold"], 0.0)
    units_l = _safe_float(rl["Units Sold"], 0.0)
    rr_e = _safe_float(re["Return Rate"], 0.0)
    rr_l = _safe_float(rl["Return Rate"], 0.0)
    np_e = _safe_float(re["Net Proceeds"], 0.0)
    np_l = _safe_float(rl["Net Proceeds"], 0.0)
    fees_e = _safe_float(re["Amazon Fees"], 0.0)
    fees_l = _safe_float(rl["Amazon Fees"], 0.0)
    sales_pct = ((sales_l - sales_e) / sales_e * 100) if sales_e else 0.0
    units_pct = ((units_l - units_e) / units_e * 100) if units_e else 0.0
    np_pct = ((np_l - np_e) / np_e * 100) if np_e else 0.0
    rr_pp = (rr_l - rr_e) * 100
    out.append(f"• Sales {sales_pct:+.1f}% from {earliest} to {latest}.")
    out.append(f"• Units sold {units_pct:+.1f}% from {earliest} to {latest}.")
    out.append(f"• Return rate change {rr_pp:+.1f}pp.")
    out.append(f"• Net proceeds {np_pct:+.1f}% from {earliest} to {latest}.")
    fees_grew_faster = False
    if sales_e and fees_e:
        sales_gr = (sales_l - sales_e) / sales_e
        fees_gr = (fees_l - fees_e) / fees_e
        fees_grew_faster = fees_gr > sales_gr
    out.append("• Fees grew faster than sales." if fees_grew_faster else "• Fees did not grow faster than sales.")
    rev_gr = (sales_l - sales_e) / sales_e if sales_e else 0.0
    profit_gr = (np_l - np_e) / np_e if np_e else 0.0
    if profit_gr < rev_gr:
        out.append("• Watchlist: profit declined faster than revenue.")
    else:
        out.append("• Watchlist: no major structural red flags in the comparison period.")
    return out


def build_yearly_kpi_df(df_base: pd.DataFrame) -> pd.DataFrame:
    if "year" not in df_base.columns:
        return pd.DataFrame(
            columns=["Year", "Units Sold", "Units Returned", "Return Rate", "Sales", "Amazon Fees", "Net Proceeds"]
        )
    rows = []
    for yr in df_base["year"].dropna().unique().tolist():
        df_y = df_base[df_base["year"] == yr].copy()
        k = compute_kpis(df_y)
        ps = safe_num(df_y["product_sales"]) if "product_sales" in df_y.columns else pd.Series(0.0, index=df_y.index)
        txn = df_y.get("txn_type", pd.Series([""] * len(df_y), index=df_y.index)).astype(str)
        sales = float(ps[bucket_mask(txn, "Order")].sum())
        fees = float(k["net_sales"] - k["net_proceeds"])
        rr = (k["units_returned"] / k["units_sold"]) if k["units_sold"] else 0.0
        rows.append({
            "Year": int(yr),
            "Units Sold": k["units_sold"],
            "Units Returned": k["units_returned"],
            "Return Rate": rr,
            "Sales": sales,
            "Amazon Fees": fees,
            "Net Proceeds": k["net_proceeds"],
        })
    return pd.DataFrame(rows)


def build_monthly_kpi_df(df_base: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df_base.columns:
        return pd.DataFrame(
            columns=["Month", "Month_Label", "Units Sold", "Units Returned", "Return Rate", "Sales", "Amazon Fees", "Net Proceeds"]
        )
    df = df_base.dropna(subset=["date"]).copy()
    if df.empty:
        return pd.DataFrame(
            columns=["Month", "Month_Label", "Units Sold", "Units Returned", "Return Rate", "Sales", "Amazon Fees", "Net Proceeds"]
        )
    df["Month"] = pd.to_datetime(df["date"]).dt.to_period("M").dt.to_timestamp()
    rows = []
    for month in sorted(df["Month"].unique()):
        df_m = df[df["Month"] == month].copy()
        k = compute_kpis(df_m)
        ps = safe_num(df_m["product_sales"]) if "product_sales" in df_m.columns else pd.Series(0.0, index=df_m.index)
        txn = df_m.get("txn_type", pd.Series([""] * len(df_m), index=df_m.index)).astype(str)
        sales = float(ps[bucket_mask(txn, "Order")].sum())
        fees = float(k["net_sales"] - k["net_proceeds"])
        rr = (k["units_returned"] / k["units_sold"]) if k["units_sold"] else 0.0
        month_label = pd.Timestamp(month).strftime("%B %Y")
        rows.append({
            "Month": month,
            "Month_Label": month_label,
            "Units Sold": k["units_sold"],
            "Units Returned": k["units_returned"],
            "Return Rate": rr,
            "Sales": sales,
            "Amazon Fees": fees,
            "Net Proceeds": k["net_proceeds"],
        })
    return pd.DataFrame(rows)


def _get_last_complete_month_start() -> pd.Timestamp:
    today = date.today()
    first_this_month = date(today.year, today.month, 1)
    last_day_prev = first_this_month - timedelta(days=1)
    ref = date(last_day_prev.year, last_day_prev.month, 1)
    return pd.Timestamp(ref)


def _comparison_metrics_ytd_exact(df_base: pd.DataFrame, max_date: pd.Timestamp) -> List[Dict]:
    if "date" not in df_base.columns or df_base.empty or pd.isna(max_date):
        return []
    df = df_base.dropna(subset=["date"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    ref = pd.Timestamp(max_date)
    current_start = pd.Timestamp(year=ref.year, month=1, day=1)
    current_end = ref
    prior_start = pd.Timestamp(year=ref.year - 1, month=1, day=1)
    prior_end = ref - pd.DateOffset(years=1)
    df_current = df[(df["date"] >= current_start) & (df["date"] <= current_end)]
    df_prior = df[(df["date"] >= prior_start) & (df["date"] <= prior_end)]
    if df_current.empty or df_prior.empty:
        return []
    if "product_sales" in df_current.columns and "txn_type" in df_current.columns:
        ps_c = safe_num(df_current["product_sales"])
        txn_c = df_current["txn_type"].astype(str)
        sales_c = float(ps_c[bucket_mask(txn_c, "Order")].sum())
    else:
        kc = compute_kpis(df_current)
        sales_c = float(kc["net_sales"])
    if "product_sales" in df_prior.columns and "txn_type" in df_prior.columns:
        ps_p = safe_num(df_prior["product_sales"])
        txn_p = df_prior["txn_type"].astype(str)
        sales_p = float(ps_p[bucket_mask(txn_p, "Order")].sum())
    else:
        kp = compute_kpis(df_prior)
        sales_p = float(kp["net_sales"])
    k_current = compute_kpis(df_current)
    k_prior = compute_kpis(df_prior)
    fees_c = float(k_current["net_sales"] - k_current["net_proceeds"])
    fees_p = float(k_prior["net_sales"] - k_prior["net_proceeds"])
    rr_c = (k_current["units_returned"] / k_current["units_sold"]) if k_current["units_sold"] else 0.0
    rr_p = (k_prior["units_returned"] / k_prior["units_sold"]) if k_prior["units_sold"] else 0.0
    ref_label = f"Jan 1–{ref.strftime('%b')} {int(ref.day)}, {ref.year}"
    prior_label = f"Jan 1–{prior_end.strftime('%b')} {int(prior_end.day)}, {prior_end.year}"
    y_cols = ["Units Sold", "Units Returned", "Return Rate", "Sales", "Amazon Fees", "Net Proceeds"]
    current_vals = [
        k_current["units_sold"], k_current["units_returned"], rr_c, sales_c, fees_c, k_current["net_proceeds"],
    ]
    prior_vals = [
        k_prior["units_sold"], k_prior["units_returned"], rr_p, sales_p, fees_p, k_prior["net_proceeds"],
    ]
    comps = []
    for i, y_col in enumerate(y_cols):
        c_val = current_vals[i]
        p_val = prior_vals[i]
        yoy = ((c_val - p_val) / p_val * 100) if p_val and p_val != 0 else None
        needs = False
        if yoy is not None:
            if y_col == "Return Rate":
                needs = yoy > 0
            else:
                needs = yoy < -10
        comps.append({
            "current_val": c_val,
            "prior_val": p_val,
            "yoy_pct": yoy,
            "ref_month_label": ref_label,
            "prior_month_label": prior_label,
            "needs_attention": needs,
            "ytd_current": c_val,
            "ytd_prior": p_val,
        })
    return comps


def _comparison_metrics(monthly_df: pd.DataFrame, y_col: str, max_date: pd.Timestamp | None = None) -> Dict:
    out = {
        "mom_pct": None, "yoy_pct": None, "ytd_current": None, "ytd_prior": None,
        "current_val": None, "prior_val": None, "ref_month_label": None, "prior_month_label": None,
        "needs_attention": False,
    }
    if monthly_df.empty or y_col not in monthly_df.columns:
        return out
    df = monthly_df.sort_values("Month").copy()
    df["Month"] = pd.to_datetime(df["Month"])
    df["year"] = df["Month"].dt.year
    df["month_num"] = df["Month"].dt.month
    if max_date is not None and pd.notna(max_date):
        ref_ts = pd.Timestamp(max_date)
        ref_year = ref_ts.year
        ref_month_num = ref_ts.month
    else:
        ref_ts = pd.Timestamp(df["Month"].max())
        ref_year = ref_ts.year
        ref_month_num = ref_ts.month
    df_current = df[(df["year"] == ref_year) & (df["month_num"] <= ref_month_num)]
    if df_current.empty:
        return out
    if y_col == "Return Rate":
        ytd_current = float(df_current[y_col].mean())
    else:
        ytd_current = float(df_current[y_col].sum())
    out["ytd_current"] = ytd_current
    out["current_val"] = ytd_current
    df_prior = df[(df["year"] == ref_year - 1) & (df["month_num"] <= ref_month_num)]
    if df_prior.empty:
        return out
    if y_col == "Return Rate":
        ytd_prior = float(df_prior[y_col].mean())
    else:
        ytd_prior = float(df_prior[y_col].sum())
    out["ytd_prior"] = ytd_prior
    out["prior_val"] = ytd_prior
    month_name = ref_ts.strftime("%b")
    out["ref_month_label"] = f"Jan–{month_name} {ref_year}"
    out["prior_month_label"] = f"Jan–{month_name} {ref_year - 1}"
    if ytd_prior is not None and ytd_prior != 0:
        out["yoy_pct"] = ((ytd_current - ytd_prior) / ytd_prior) * 100
    if out.get("yoy_pct") is not None and out["yoy_pct"] < -10:
        out["needs_attention"] = True
    s = df.set_index("Month")[y_col]
    if len(s) >= 2:
        prev_month_ts = ref_ts - pd.DateOffset(months=1)
        if prev_month_ts in s.index and s.loc[prev_month_ts] and s.loc[prev_month_ts] != 0:
            C = float(s.loc[ref_ts])
            out["mom_pct"] = ((C - float(s.loc[prev_month_ts])) / float(s.loc[prev_month_ts])) * 100
    return out


def _comparison_badge_html(mom_pct: float | None, yoy_pct: float | None, prefer: str = "yoy") -> str:
    pct = yoy_pct if prefer == "yoy" and yoy_pct is not None else mom_pct
    if pct is None:
        return ""
    pct = _safe_float(pct, 0.0)
    label = "YoY" if (prefer == "yoy" and yoy_pct is not None) else "MoM"
    up = pct >= 0
    arrow = "↑" if up else "↓"
    cls = "flip-badge-up" if up else "flip-badge-down"
    return f'<span class="flip-comp-badge {cls}">{arrow} {abs(pct):.1f}% {label}</span>'


# ----------------------------
# Page config / title
# ----------------------------
st.set_page_config(page_title="Key Performance Indicator", layout="wide")

st.markdown(
    """
    <style>
    .kpi-page-title { font-size: 2.75rem !important; font-weight: 700; color: #1f2937; margin-bottom: 0.5rem; }
    [data-testid="stMultiSelect"] { margin-top: 1rem !important; }
    [data-testid="stMultiSelect"] label { font-size: 1.5rem !important; }
    [data-testid="stMultiSelect"] > div { margin-top: 0.5rem !important; }
    [data-testid="stMultiSelect"], [data-testid="stMultiSelect"] * { font-size: 1.5rem !important; }
    .exec-summary-title { font-size: 1.75rem !important; font-weight: 700; margin-bottom: 0.5rem; }
    .exec-summary-bullet { font-size: 1.375rem !important; margin: 0.4em 0; }
    .exec-bullet-dot { margin-right: 0.5em; display: inline-block; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown("<h1 class='kpi-page-title'>Key Performance Indicator</h1>", unsafe_allow_html=True)

# ----------------------------
# Require uploaded data
# ----------------------------
if "df_processed" not in st.session_state or st.session_state.df_processed is None:
    st.info("Upload a file on the main page first. Then return to this page.")
    st.stop()

df_base = st.session_state.df_processed.copy()
if "txn_type" not in df_base.columns:
    df_base["txn_type"] = ""
if "date" not in df_base.columns and "date_time" in df_base.columns:
    df_base["date"] = pd.to_datetime(df_base["date_time"], errors="coerce")
else:
    df_base["date"] = pd.to_datetime(df_base["date"], errors="coerce")
df_base["year"] = df_base["date"].dt.year

available_years: List[int] = sorted(
    [int(y) for y in df_base["year"].dropna().unique().tolist() if pd.notna(y)]
)
if not available_years:
    st.error("No valid dates found. Ensure date_time is parseable.")
    st.stop()

# ----------------------------
# Year filter
# ----------------------------
if "kpi_selected_years" not in st.session_state:
    st.session_state.kpi_selected_years = list(available_years)
selected_years = st.multiselect(
    "Select Year",
    options=available_years,
    default=st.session_state.kpi_selected_years,
    key="kpi_selected_years",
)
if not selected_years:
    selected_years = list(available_years)
mask = df_base["year"].isin(selected_years)
df_scope = df_base[mask].copy()
if df_scope.empty:
    st.warning("No data for selected years.")
    st.stop()

kpis = compute_kpis(df_scope)
sales_series = safe_num(df_scope["product_sales"]) if "product_sales" in df_scope.columns else pd.Series(0.0, index=df_scope.index)
txn_series = df_scope.get("txn_type", pd.Series([""] * len(df_scope), index=df_scope.index)).astype(str)
is_order = bucket_mask(txn_series, "Order")
is_refund = bucket_mask(txn_series, "Refund")
sales_order = float(sales_series[is_order].sum())
sales_refund = float(sales_series[is_refund].sum())
sales_refund_abs = abs(sales_refund)
return_rate = (kpis["units_returned"] / kpis["units_sold"]) if kpis["units_sold"] else 0.0
total_amazon_fees = float(kpis["net_sales"] - kpis["net_proceeds"])

# ----------------------------
# Dynamic year subtitle
# ----------------------------
if len(selected_years) == 1:
    year_subtitle = str(int(selected_years[0]))
elif len(selected_years) == 2:
    year_subtitle = f"{int(selected_years[0])} and {int(selected_years[1])}"
else:
    year_subtitle = ", ".join(str(int(y)) for y in selected_years[:-1]) + ", and " + str(int(selected_years[-1]))

yearly_df = build_yearly_kpi_df(df_base)
monthly_df = build_monthly_kpi_df(df_base)
CHART_HEIGHT = 220
years_in_data = sorted(monthly_df["Month"].dt.year.unique()) if not monthly_df.empty else []
x_tickvals = [pd.Timestamp(y, 1, 1) for y in years_in_data]
x_ticktext = [str(y) for y in years_in_data]


def _monthly_trend_chart(y_col: str, df: pd.DataFrame) -> px.Figure:
    fig = px.line(df, x="Month", y=y_col, markers=True, custom_data=["Month_Label"])
    fig.update_traces(
        line_color=TEAL, line_shape="spline", line=dict(width=4), marker=dict(size=8),
    )
    if not df.empty and y_col in df.columns:
        avg_val = df[y_col].mean()
        fig.add_hline(y=avg_val, line_dash="dot", line_color="rgba(100,100,100,0.7)", line_width=1.5)
    dfc = df.copy()
    dfc["Month"] = pd.to_datetime(dfc["Month"])
    dfc["Year"] = dfc["Month"].dt.year
    years = sorted(dfc["Year"].unique())
    if len(years) >= 2:
        prev_year = years[-2]
        df_ly = dfc[dfc["Year"] == prev_year]
        if not df_ly.empty:
            fig.add_trace(
                go.Scatter(
                    x=df_ly["Month"],
                    y=df_ly[y_col],
                    mode="lines",
                    line=dict(color="rgba(180,180,180,0.85)", width=2, dash="dash"),
                    name="Prior year",
                    showlegend=False,
                )
            )
    axis_font_size = 26
    fig.update_layout(
        height=CHART_HEIGHT,
        margin=dict(t=50, b=58, l=88, r=24),
        xaxis=dict(
            type="date", title="", tickfont=dict(size=axis_font_size), showgrid=False, showline=False,
            zeroline=False, mirror=False, tickmode="array", tickvals=x_tickvals, ticktext=x_ticktext,
            range=[df["Month"].min() - pd.Timedelta(days=15), df["Month"].max() + pd.Timedelta(days=15)] if len(df) > 0 else None,
            automargin=True, ticklabelstandoff=10,
        ),
        yaxis=dict(
            title="", tickfont=dict(size=axis_font_size), showgrid=False, showline=False, zeroline=False,
            mirror=False, showticklabels=True, automargin=True, ticklabelstandoff=14, ticklabelposition="outside",
        ),
        showlegend=False,
        font=dict(size=10),
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor="white", font_size=18, font_family="Inter, sans-serif",
            font=dict(size=18, color="#1f2937", family="Inter, sans-serif", weight="bold"),
            bordercolor="#e0e0e0", align="left",
        ),
    )
    return fig


def _format_metric_value(value: float, y_fmt: str) -> str:
    value = _safe_float(value, 0.0)
    if y_fmt == ".1%":
        return f"{value:.1%}"
    if y_fmt == "$,.0f":
        return f"${value:,.0f}"
    return f"{value:,.0f}"


def _flip_back_summary(
    monthly_df: pd.DataFrame, y_col: str, metric_label: str, comp: Dict,
    sales_yoy_pct: float | None = None, y_fmt: str = ",.0f",
) -> Dict:
    empty_result = {
        "snapshot": "No data available for summary.", "diagnostic": "—", "action_plan": "—",
        "status": "Healthy", "prior_month_label": None, "ref_month_label": None,
        "prior_val": None, "current_val": None, "value_fmt": y_fmt,
    }
    if monthly_df.empty or y_col not in monthly_df.columns:
        return empty_result
    yoy_raw = comp.get("yoy_pct")
    yoy = _safe_float(yoy_raw, 0.0) if yoy_raw is not None else None
    mom_raw = comp.get("mom_pct")
    mom = _safe_float(mom_raw, 0.0) if mom_raw is not None else None
    needs_attention = comp.get("needs_attention", False)
    if y_col == "Return Rate" and yoy is not None and yoy > 0:
        needs_attention = True
    status = "Needs Attention" if needs_attention else "Healthy"
    ref_label = comp.get("ref_month_label")
    prior_label = comp.get("prior_month_label")
    metric_name = metric_label.replace(" ($)", "").strip()
    if ref_label and prior_label and yoy is not None:
        snapshot = f"Showing YTD ({ref_label}) vs same period last year ({prior_label}). {metric_name} changed by {yoy:+.1f}%."
    elif ref_label and prior_label:
        snapshot = f"Showing YTD ({ref_label}) vs same period last year ({prior_label}). YoY not available."
    else:
        snapshot = "Insufficient data for YTD comparison."
    diagnostic = "—"
    if yoy is not None and mom is not None:
        if yoy < 0 and mom > 0:
            diagnostic = "Positive monthly recovery noted, though still trailing behind last year's performance levels."
        elif "Return" in metric_label or y_col in ("Units Returned", "Return Rate"):
            diagnostic = "Return volume is higher than historical norms for this period; investigate recent batch quality or shipping damage." if yoy and yoy > 0 else "Return levels are in line with or below prior year; monitor for seasonal shifts."
        elif "Amazon Fees" in metric_label or y_col == "Amazon Fees":
            diagnostic = "Fee-to-revenue efficiency is declining. Analyze FBA fulfillment vs. storage fee increases." if sales_yoy_pct is not None and yoy and yoy > sales_yoy_pct else "Fees are tracking with or better than sales growth; continue monitoring FBA and referral fee changes."
        elif "Sales" in metric_label or "Net Proceeds" in metric_label or y_col in ("Sales", "Net Proceeds"):
            diagnostic = "Performance reflects demand, pricing, and cost structure; compare to campaign and inventory decisions."
        else:
            diagnostic = "Trend reflects seasonality and operational factors; compare to prior year for context."
    elif yoy is not None:
        if "Units Sold" in metric_label or y_col == "Units Sold":
            diagnostic = f"YTD is {abs(yoy):.1f}% below the same period last year; review demand, inventory, and promotions against historical levels." if yoy < 0 else f"YTD is {yoy:.1f}% above the same period last year; performance is ahead of historical levels for this period."
        elif "Return" in metric_label or y_col in ("Units Returned", "Return Rate"):
            diagnostic = "YTD return volume is higher than historical norms for this period; investigate batch quality or shipping feedback." if yoy and yoy > 0 else "YTD return levels are below the same period last year; continue monitoring against historical benchmarks."
        elif "Sales" in metric_label or y_col == "Sales":
            diagnostic = f"YTD sales are {abs(yoy):.1f}% below the same period last year; compare to historical levels and adjust promotions or pricing." if yoy < 0 else f"YTD sales are {yoy:.1f}% above the same period last year; ahead of historical levels."
        elif "Amazon Fees" in metric_label or y_col == "Amazon Fees":
            diagnostic = "YTD fees are higher than the same period last year; review FBA and storage mix against historical cost levels." if yoy and yoy > 0 else "YTD fees are below the same period last year; efficiency is better than historical levels."
        elif "Net Proceeds" in metric_label or y_col == "Net Proceeds":
            diagnostic = f"YTD net proceeds are {abs(yoy):.1f}% below the same period last year; compare to historical performance and margin drivers." if yoy < 0 else f"YTD net proceeds are {yoy:.1f}% above the same period last year; ahead of historical levels."
        else:
            diagnostic = f"YTD is {abs(yoy):.1f}% below the same period last year; compare to historical levels for context." if yoy < 0 else f"YTD is {yoy:.1f}% above the same period last year."
    action_plan = "—"
    if "Units Sold" in metric_label or y_col == "Units Sold":
        action_plan = "Audit Q1 advertising spend and inventory availability to support volume."
    elif "Return" in metric_label or y_col in ("Units Returned", "Return Rate"):
        action_plan = "Review recent batches and shipping practices; tighten quality checks if needed."
    elif "Sales" in metric_label or y_col == "Sales":
        action_plan = "Audit Q1 advertising spend and promotions for revenue impact."
    elif "Amazon Fees" in metric_label or y_col == "Amazon Fees":
        action_plan = "Adjust pricing to offset increased Amazon fulfillment costs; review storage and FBA mix."
    elif "Net Proceeds" in metric_label or y_col == "Net Proceeds":
        action_plan = "Optimize fee structure and promotions to protect margin; review COGS and fulfillment mix."
    return {
        "snapshot": snapshot, "diagnostic": diagnostic, "action_plan": action_plan, "status": status,
        "prior_month_label": prior_label, "ref_month_label": ref_label,
        "prior_val": comp.get("prior_val"), "current_val": comp.get("current_val"), "value_fmt": y_fmt,
    }


def _flip_back_yoy_bars(
    prior_label: str | None, ref_label: str | None, prior_val: float | None, current_val: float | None, value_fmt: str,
) -> str:
    if prior_label is None or ref_label is None or prior_val is None or current_val is None:
        return ""
    prior_val = _safe_float(prior_val, 0.0)
    current_val = _safe_float(current_val, 0.0)
    max_val = max(prior_val, current_val) or 1
    pct_prior = (prior_val / max_val) * 100
    pct_current = (current_val / max_val) * 100
    prior_str = _format_metric_value(prior_val, value_fmt)
    current_str = _format_metric_value(current_val, value_fmt)
    return f"""
    <div class="flip-back-yoy-bars">
    <div class="flip-yoy-bar-item">
    <div class="flip-yoy-value">{html.escape(prior_str)}</div>
    <div class="flip-yoy-bar-wrap"><div class="flip-yoy-bar flip-yoy-prior" style="width:{pct_prior:.0f}%"></div></div>
    <div class="flip-yoy-label">{html.escape(prior_label)}</div>
    </div>
    <div class="flip-yoy-bar-item">
    <div class="flip-yoy-value">{html.escape(current_str)}</div>
    <div class="flip-yoy-bar-wrap"><div class="flip-yoy-bar flip-yoy-current" style="width:{pct_current:.0f}%"></div></div>
    <div class="flip-yoy-label">{html.escape(ref_label)}</div>
    </div>
    </div>
    """


def _flip_back_html(back_data: Dict) -> str:
    snapshot = back_data.get("snapshot", "")
    diagnostic = back_data.get("diagnostic", "")
    action_plan = back_data.get("action_plan", "")
    status = back_data.get("status", "Healthy")
    badge_cls = "flip-badge-good" if status == "Healthy" else "flip-badge-attention"
    badge_html = f'<div class="flip-back-status-badge {badge_cls}">{html.escape(status)}</div>'
    bar_html = _flip_back_yoy_bars(
        back_data.get("prior_month_label"), back_data.get("ref_month_label"),
        back_data.get("prior_val"), back_data.get("current_val"),
        back_data.get("value_fmt", ",.0f"),
    )
    parts = [
        f'<div class="flip-back-section"><strong>Snapshot</strong><div class="flip-back-bullet"><span class="flip-bullet-dot">•</span> {html.escape(snapshot)}</div></div>',
        f'<div class="flip-back-section flip-back-yoy-section">{bar_html}</div>' if bar_html else "",
        f'<div class="flip-back-section"><strong>Diagnostic</strong><div class="flip-back-bullet"><span class="flip-bullet-dot">•</span> {html.escape(diagnostic)}</div></div>',
        f'<div class="flip-back-section"><strong>Action Plan</strong><div class="flip-back-bullet"><span class="flip-bullet-dot">•</span> {html.escape(action_plan)}</div></div>',
    ]
    return f'<div class="flip-back-content-inner">{badge_html}<div class="flip-back-sections">{"".join(parts)}</div></div>'


def _build_flip_card_html(
    year_subtitle: str,
    kpis: Dict,
    return_rate: float,
    sales_order: float,
    total_amazon_fees: float,
    monthly_df: pd.DataFrame,
    max_date: pd.Timestamp | None = None,
    df_base: pd.DataFrame | None = None,
) -> str:
    us = _safe_float(kpis.get("units_sold"), 0.0)
    ur = _safe_float(kpis.get("units_returned"), 0.0)
    rr = _safe_float(return_rate, 0.0)
    so = _safe_float(sales_order, 0.0)
    taf = _safe_float(total_amazon_fees, 0.0)
    np = _safe_float(kpis.get("net_proceeds"), 0.0)
    cards_data = [
        ("TOTAL UNITS SOLD", f"{us:,.0f}", "", "Units Sold", ",.0f", " %{customdata[0]}: %{y:,.0f} "),
        ("TOTAL UNITS RETURNED", f"{ur:,.0f}", "", "Units Returned", ",.0f", " %{customdata[0]}: %{y:,.0f} "),
        ("RETURN RATE", f"{rr:.1%}", " kpi-value-underline", "Return Rate", ".1%", " %{customdata[0]}: %{y:.1%} "),
        ("TOTAL UNITS SALES ($)", f"${so:,.0f}", "", "Sales", "$,.0f", " %{customdata[0]}: $%{y:,.0f} "),
        ("TOTAL AMAZON FEES ($)", f"${taf:,.0f}", "", "Amazon Fees", "$,.0f", " %{customdata[0]}: $%{y:,.0f} "),
        ("NET PROCEEDS ($)", f"${np:,.0f}", "", "Net Proceeds", "$,.0f", " %{customdata[0]}: $%{y:,.0f} "),
    ]
    chart_htmls = []
    if not monthly_df.empty:
        for i, (title, value, value_class, y_col, y_fmt, hover_tpl) in enumerate(cards_data):
            fig = _monthly_trend_chart(y_col, monthly_df)
            fig.update_traces(hovertemplate=f"<b>{hover_tpl}</b><extra></extra>")
            fig.update_layout(yaxis_tickformat=y_fmt)
            chart_htmls.append(pio.to_html(fig, full_html=False, include_plotlyjs=False, div_id=f"flip_chart_{i}"))
    else:
        chart_htmls = ["<div></div>"] * 6

    y_cols = ["Units Sold", "Units Returned", "Return Rate", "Sales", "Amazon Fees", "Net Proceeds"]
    if df_base is not None and not df_base.empty and max_date is not None and pd.notna(max_date) and "date" in df_base.columns:
        comps = _comparison_metrics_ytd_exact(df_base, pd.Timestamp(max_date))
        if len(comps) != 6:
            comps = [_comparison_metrics(monthly_df, y_cols[i], max_date=max_date) for i in range(6)] if not monthly_df.empty else [{} for _ in range(6)]
    else:
        comps = [_comparison_metrics(monthly_df, y_cols[i], max_date=max_date) for i in range(6)] if not monthly_df.empty else [{} for _ in range(6)]
    sales_yoy = comps[3].get("yoy_pct") if len(comps) > 3 else None
    back_htmls = []
    for i in range(6):
        title, _, _, y_col, y_fmt, _ = cards_data[i]
        y_col = y_cols[i] if i < len(y_cols) else y_col
        comp = comps[i] if i < len(comps) else {}
        sales_yoy_pct = sales_yoy if y_col == "Amazon Fees" else None
        back_data = _flip_back_summary(monthly_df, y_col, title, comp, sales_yoy_pct=sales_yoy_pct, y_fmt=y_fmt)
        back_htmls.append(_flip_back_html(back_data))

    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    * { box-sizing: border-box; }
    .flip-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; max-width: 100%; font-family: 'Inter', sans-serif; }
    .flip-card-outer { min-height: 460px; }
    .flip-card { position: relative; width: 100%; min-height: 460px; cursor: pointer; perspective: 1200px; }
    .flip-card-inner { position: relative; width: 100%; min-height: 460px; transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); transform-style: preserve-3d; }
    .flip-card.flipped .flip-card-inner { transform: rotateY(180deg); }
    .flip-card-front, .flip-card-back { position: absolute; width: 100%; min-height: 460px; left: 0; top: 0; backface-visibility: hidden; -webkit-backface-visibility: hidden; border: 2.5px solid #666666; border-radius: 12px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.18), 0 10px 20px rgba(0,0,0,0.14); background: #fff; display: flex; flex-direction: column; }
    .flip-card-back { transform: rotateY(180deg); background: #fff; display: flex; flex-direction: column; }
    .flip-header { background: #0f766e; color: #fff; padding: 1rem; text-align: center; border-radius: 12px 12px 0 0; }
    .flip-title { font-size: 34px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin: 0; padding-bottom: 4px; border-bottom: 2px solid #fff; display: inline-block; }
    .flip-subtitle { font-size: 26px; color: #fff; margin-top: 6px; margin-bottom: 0; }
    .flip-value-wrap { background: #fff; padding: 1.25rem 1rem; text-align: center; }
    .flip-value { font-size: 36px; font-weight: 800; color: #0f172a; margin: 0; letter-spacing: 0.02em; font-variant-numeric: tabular-nums; }
    .flip-value-underline { text-decoration: underline; text-underline-offset: 10px; }
    .flip-chart-divider { margin-top: 0.25rem; border-top: 2px solid #666666; padding-top: 0.5rem; }
    .flip-chart-wrap { flex: 1; min-height: 220px; padding: 0 8px 1rem; }
    .flip-chart-wrap > div { width: 100% !important; }
    .flip-card-back .flip-back-header { background: #0f766e; color: #fff; padding: 1rem; text-align: center; border-radius: 12px 12px 0 0; }
    .flip-card-back .flip-back-title { font-size: 34px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin: 0; padding-bottom: 4px; border-bottom: 2px solid #fff; display: inline-block; }
    .flip-card-back .flip-back-subtitle { font-size: 26px; color: #fff; margin-top: 6px; margin-bottom: 0; }
    .flip-value-wrap { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 0.5rem; }
    .flip-comp-badge-wrap { flex-shrink: 0; }
    .flip-comp-badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 6px; font-weight: 700; font-size: 14px; }
    .flip-comp-badge.flip-badge-up { background: #059669; color: #fff; }
    .flip-comp-badge.flip-badge-down { background: #b91c1c; color: #fff; }
    .flip-back-content { padding: 1.25rem 1rem; font-size: 13px; line-height: 1.6; color: #1f2937; flex: 1; }
    .flip-back-content-inner { position: relative; padding-right: 8rem; }
    .flip-back-status-badge { position: absolute; top: 0; right: 0; padding: 0.35rem 0.75rem; border-radius: 6px; font-weight: 700; font-size: 13px; }
    .flip-back-status-badge.flip-badge-good { background: #0f766e; color: #fff; }
    .flip-back-status-badge.flip-badge-attention { background: #b91c1c; color: #fff; }
    .flip-back-sections { margin-top: 0.25rem; }
    .flip-back-section { margin-bottom: 0.6rem; }
    .flip-back-bullet { margin-bottom: 0.35rem; }
    .flip-bullet-dot { margin-right: 0.35em; }
    .flip-back-yoy-section { margin-top: 0.5rem; margin-bottom: 0.5rem; }
    .flip-back-yoy-bars { display: flex; gap: 1rem; align-items: flex-end; justify-content: center; min-height: 72px; }
    .flip-yoy-bar-item { flex: 1; max-width: 50%; display: flex; flex-direction: column; align-items: center; }
    .flip-yoy-value { font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 4px; }
    .flip-yoy-bar-wrap { width: 100%; height: 24px; background: #e5e7eb; border-radius: 4px; overflow: hidden; }
    .flip-yoy-bar { height: 100%; border-radius: 4px; min-width: 4px; }
    .flip-yoy-prior { background: #9ca3af; }
    .flip-yoy-current { background: #0f766e; }
    .flip-yoy-label { font-size: 12px; color: #6b7280; margin-top: 4px; }
    </style>
    """
    script = '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>'
    rows = []
    for i in range(6):
        title, value, value_class, _, _, _ = cards_data[i]
        chart_block = chart_htmls[i] if i < len(chart_htmls) else "<div></div>"
        back_body = back_htmls[i] if i < len(back_htmls) else ""
        rows.append(f"""
    <div class="flip-card-outer">
    <div class="flip-card" onclick="this.classList.toggle('flipped')">
    <div class="flip-card-inner">
    <div class="flip-card-front">
    <div class="flip-header">
    <div class="flip-title">{html.escape(title)}</div>
    <div class="flip-subtitle">{html.escape(year_subtitle)}</div>
    </div>
    <div class="flip-value-wrap">
    <div class="flip-value{value_class}">{html.escape(value)}</div>
    </div>
    <div class="flip-chart-divider"></div>
    <div class="flip-chart-wrap" onclick="event.stopPropagation()">{chart_block}</div>
    </div>
    <div class="flip-card-back">
    <div class="flip-back-header">
    <div class="flip-back-title">{html.escape(title)}</div>
    <div class="flip-back-subtitle">Summary</div>
    </div>
    <div class="flip-back-content">{back_body}</div>
    </div>
    </div>
    </div>
    </div>
    """)
    grid = f'<div class="flip-grid">{"".join(rows)}</div>'
    return f"<!DOCTYPE html><html><head>{css}</head><body>{script}{grid}</body></html>"


# ----------------------------
# Flip cards: 6 Metric Widgets (3x2 grid)
# ----------------------------
max_date_in_file = df_base["date"].max() if "date" in df_base.columns and not df_base.empty else None
if pd.isna(max_date_in_file):
    max_date_in_file = None
flip_html = _build_flip_card_html(
    year_subtitle, kpis, return_rate, sales_order, total_amazon_fees, monthly_df,
    max_date=max_date_in_file, df_base=df_base,
)
components.html(flip_html, height=960, scrolling=False)

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
st.markdown("<div style='margin: 0;'><hr style='margin: 0; border: 0; border-top: 1px solid #ccc;'/></div>", unsafe_allow_html=True)

summary_lines = generate_summary(selected_years, yearly_df)
exec_html = "<div class='exec-summary-section'><h3 class='exec-summary-title'>Executive Summary</h3>"
for line in summary_lines:
    text = line[2:] if line.startswith("• ") else line
    exec_html += f"<p class='exec-summary-bullet'><span class='exec-bullet-dot'>•</span><span class='exec-bullet-text'>{html.escape(text)}</span></p>"
exec_html += "</div>"
st.markdown(exec_html, unsafe_allow_html=True)
