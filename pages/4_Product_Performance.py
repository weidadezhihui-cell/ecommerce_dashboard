"""
Amazon Settlement - Analysis by Product
PowerBI-style in-dashboard slicers + YoY overlay charts (Jan–Dec, line per year)
"""

from __future__ import annotations

import calendar
import html
from typing import Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import to_money

# Readability: chart HTML titles & Plotly fonts (axis, tick, legend, bar/pie labels)
CHART_TITLE_TOP_PX = 20
CHART_TITLE_MID_PX = 19
CHART_TITLE_BOT_PX = 18
CHART_AXIS_TITLE_PT = 18
CHART_TICK_PT = 16
CHART_LEGEND_PT = 16
CHART_BAR_TEXT_PT = 16
CHART_PIE_TEXT_PT = 16

# Monthly YoY line chart height (taller for clearer trend)
CHART_YOY_HEIGHT_PX = 580


def _three_line_chart_title_html(top: str, middle: str, bottom: str) -> str:
    """Shared HTML for three-line chart headers (line breaks + spacing between lines)."""
    return (
        f"<span style='font-size:{CHART_TITLE_TOP_PX}px;font-weight:600;line-height:1.42;color:#1f2937'>"
        f"{html.escape(top)}</span><br><br>"
        f"<span style='font-size:{CHART_TITLE_MID_PX}px;font-weight:700;line-height:1.48;color:#1f2937'>"
        f"{html.escape(middle)}</span><br><br>"
        f"<span style='font-size:{CHART_TITLE_BOT_PX}px;font-weight:400;line-height:1.48;color:#1f2937'>"
        f"{html.escape(bottom)}</span>"
    )


def _plotly_three_line_centered_title(top: str, middle: str, bottom: str) -> dict:
    """Plotly layout title dict (bar/pie). YoY line chart uses Streamlit heading instead — see below."""
    return {
        "text": _three_line_chart_title_html(top, middle, bottom),
        "x": 0.5,
        "xanchor": "center",
    }


# YoY chart colors vs max year in view (newest = KPI dark teal; vibrant palette for contrast)
_BRAND_TEAL = "#0f766e"
_VIBRANT_SKY_BLUE = "#0EA5E9"
_EMERALD_GREEN = "#10B981"


def brand_color_for_year(year: int, max_year: int) -> str:
    """Newest year = dark teal; max-1 = sky blue; max-2 and older = emerald green."""
    if year == max_year:
        return _BRAND_TEAL
    if year == max_year - 1:
        return _VIBRANT_SKY_BLUE
    if year <= max_year - 2:
        return _EMERALD_GREEN
    return _EMERALD_GREEN


def _kpi_info_tooltip(explanation: str) -> str:
    """Native HTML title tooltip (ℹ️) for KPI definitions."""
    return (
        f'<span class="product-kpi-info" role="img" aria-label="{html.escape(explanation)}" '
        f'title="{html.escape(explanation)}">&#8505;&#65039;</span>'
    )


# ----------------------------
# Page config / title (styles aligned with Key Performance Indicator page)
# ----------------------------
st.set_page_config(page_title="Product Performance", layout="wide")
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" '
    'crossorigin="anonymous" referrerpolicy="no-referrer"/>',
    unsafe_allow_html=True,
)
st.markdown(
    """
    <style>
    .kpi-page-title { font-size: 2.75rem !important; font-weight: 700; color: #1f2937; margin-bottom: 0.35rem !important; }
    .product-page-subtitle { font-size: 1.25rem !important; color: #6b7280; margin-bottom: 0.4rem !important; }
    /* Section headers — dark teal to match Key Performance Indicator page */
    .product-section-title { font-size: 1.75rem !important; font-weight: 700; color: #0f766e !important; margin-top: 1rem; margin-bottom: 0.5rem; }
    /* Power BI–style tiles: bordered containers from st.container(border=True) */
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-product-tile="kpi"]),
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-product-tile="viz"]),
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-product-tile="ai"]) {
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        box-shadow: rgba(0, 0, 0, 0.05) 0px 1px 3px 0px !important;
        background: #ffffff !important;
        padding: 1.35rem 1.5rem 1.5rem 1.5rem !important;
        margin-bottom: 1.25rem !important;
    }
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-product-tile="kpi"]) div[data-testid="stHorizontalBlock"] {
        justify-content: center !important;
        max-width: 1400px;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    /* Nested chart tiles — Power BI–style elevated cards (visible outer shadow) */
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-chart-tile="yoy"]),
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-chart-tile="bar"]),
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-chart-tile="pie"]) {
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        background: #ffffff !important;
        padding: 0.85rem 1rem 1rem 1rem !important;
        overflow: visible !important;
        /* Fluent / Power BI–like layered elevation */
        box-shadow:
            0 0.5px 1.5px rgba(15, 23, 42, 0.12),
            0 2px 6px rgba(15, 23, 42, 0.08),
            0 8px 20px rgba(15, 23, 42, 0.07) !important;
    }
    /* YoY card: three-line title + chart inside one bordered tile (extra top padding for headings) */
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-chart-tile="yoy"]) {
        margin-bottom: 1.35rem !important;
        margin-top: 2px !important;
        padding: 1.05rem 1.15rem 1.15rem 1.15rem !important;
    }
    .product-yoy-chart-block {
        width: 100%;
    }
    /* YoY title block — Streamlit HTML above the Plotly iframe (not layout.title) */
    .product-yoy-chart-heading {
        text-align: center;
        margin: 0 0 0.45rem 0 !important;
        padding: 0.1rem 0.5rem 0.2rem 0.5rem !important;
        position: relative;
        z-index: 1;
        background: #ffffff;
    }
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-chart-tile="bar"]),
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-chart-tile="pie"]) {
        margin-top: 2px !important;
        margin-bottom: 2px !important;
    }
    /* Let chart-card shadows paint outside the Visualizations panel */
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has([data-product-tile="viz"]) {
        overflow: visible !important;
    }
    /* Section titles sit above tiles (not inside the bordered box) */
    h2.product-section-title { margin-bottom: 0.5rem !important; }
    .product-kpi-label { font-size: 1.25rem !important; font-weight: 600 !important; color: #0f766e !important; line-height: 1.35 !important; display: flex !important; align-items: center; justify-content: center; flex-wrap: wrap; gap: 0.3rem; }
    .product-kpi-icon { color: #0f766e !important; opacity: 0.92; font-size: 1.05em; }
    .product-kpi-info { cursor: help; font-size: 0.95rem; opacity: 0.75; vertical-align: middle; }
    .product-kpi-info:hover { opacity: 1; }
    .product-kpi-value { font-size: 2rem !important; font-weight: 800 !important; color: #111827 !important; line-height: 1.2 !important; letter-spacing: -0.02em; }
    .product-kpi-sub { font-size: 1.15rem !important; font-weight: 500 !important; color: #4b5563 !important; line-height: 1.4 !important; }
    .product-kpi-cell { text-align: center; padding: 0.35rem 0.25rem; }
    /* Year multiselect chips: soft slate (not error red) */
    section[data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="tag"] {
        background-color: #F1F5F9 !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
    }
    section[data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="tag"] span {
        color: #1e293b !important;
    }
    section[data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="tag"] [role="button"],
    section[data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="tag"] svg {
        color: #475569 !important;
        fill: #475569 !important;
    }
    /* Filters: widget labels + values (scaled up vs prior 1.5rem / 1.25rem) */
    [data-testid="stSelectbox"] label, [data-testid="stSelectbox"] [data-testid="stWidgetLabel"], [data-testid="stSelectbox"] [data-testid="stWidgetLabel"] p,
    [data-testid="stMultiSelect"] label, [data-testid="stMultiSelect"] [data-testid="stWidgetLabel"], [data-testid="stMultiSelect"] [data-testid="stWidgetLabel"] p { font-size: 1.625rem !important; font-weight: 600 !important; line-height: 1.45 !important; }
    [data-testid="stSelectbox"], [data-testid="stMultiSelect"] { width: 100% !important; max-width: 100% !important; min-width: 0 !important; margin-top: 0 !important; margin-bottom: 0 !important; }
    [data-testid="stSelectbox"] label + div, [data-testid="stMultiSelect"] > div, [data-testid="stMultiSelect"] > div > div { width: 100% !important; min-height: 3.25rem !important; padding: 0.5rem 0.75rem !important; box-sizing: border-box !important; }
    [data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input, [data-testid="stMultiSelect"] [data-testid="stWidgetValue"] { font-size: 1.375rem !important; }
    [data-testid="stMultiSelect"] [data-baseweb="tag"] { font-size: 1rem !important; }
    [data-testid="stCaptionContainer"] { font-size: 1.3125rem !important; line-height: 1.5 !important; }
    /* Analyze section: radio option labels */
    section[data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] label,
    section[data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] label p,
    section[data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] label span { font-size: 1.125rem !important; line-height: 1.45 !important; }
    /* AI summary + footnote */
    section[data-testid="stMain"] [data-testid="stAlert"] { font-size: 1.125rem !important; line-height: 1.55 !important; }
    section[data-testid="stMain"] [data-testid="stAlert"] p { font-size: 1.125rem !important; }
    /* Transaction Bucket + Metric radios: selected state = brand teal */
    section[data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] label[data-baseweb="radio"] input:checked + div {
        background-color: #0f766e !important;
        border-color: #0f766e !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown("<h1 class='kpi-page-title'>Product Performance</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='product-page-subtitle'>Amazon Settlement · Compare transaction trends across years (Jan–Dec overlay)</p>",
    unsafe_allow_html=True,
)

# ----------------------------
# Helpers
# ----------------------------
MONTH_ORDER = list(range(1, 13))
MONTH_ABBR = [calendar.month_abbr[m] for m in MONTH_ORDER]


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


def _is_placeholder(val) -> bool:
    """Return True if val is nan, None, or empty (should not be shown in UI)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return True
    s = str(val).strip().lower()
    return s in ("", "nan", "none", "<na>")


def sanitize_display(val, fallback: str = "All Products") -> str:
    """Return a safe display string; replace placeholders with fallback."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return fallback
    s = str(val).strip()
    if s.lower() in ("nan", "none", "<na>"):
        return fallback
    return s if s else fallback


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
    rows = int(len(df))

    return {
        "units_sold": units_sold,
        "units_returned": units_returned,
        "net_units": net_units,
        "net_sales": net_sales,
        "net_proceeds": net_proceeds,
        "rows": rows,
    }


def human_metric_label(metric: str) -> str:
    if metric == "units":
        return "Units (Quantity)"
    if metric == "sales":
        return "Sales ($)"
    if metric == "net_proceeds":
        return "Net Proceeds ($)"
    return metric


# Third line of chart titles: Transaction Bucket × Metric (UI radio labels)
_CHART_TITLE_METRIC_PHRASES: Dict[tuple[str, str], str] = {
    ("Order", "Units (Quantity)"): "Units Ordered",
    ("Order", "Sales ($)"): "Gross Sales Revenue ($)",
    ("Order", "Net Proceeds ($)"): "Net Proceeds from Orders ($)",
    ("Refund", "Units (Quantity)"): "Units Refunded",
    ("Refund", "Sales ($)"): "Total Refunded Amount ($)",
    ("Refund", "Net Proceeds ($)"): "Net Refund Cost ($)",
    ("Liquidations", "Units (Quantity)"): "Liquidated Units",
    ("Liquidations", "Sales ($)"): "Gross Liquidation Value ($)",
    ("Liquidations", "Net Proceeds ($)"): "Net Proceeds from Liquidations ($)",
    ("Adjustment", "Units (Quantity)"): "Inventory Adjustments (Units)",
    ("Adjustment", "Sales ($)"): "Gross Adjustment Value ($)",
    ("Adjustment", "Net Proceeds ($)"): "Net Proceeds from Adjustments ($)",
}


def chart_title_metric_phrase(txn_bucket: str, selected_metric_ui: str, fallback: str) -> str:
    """Natural-sounding subtitle for charts from Transaction Bucket × Metric radios."""
    return _CHART_TITLE_METRIC_PHRASES.get((txn_bucket, selected_metric_ui), fallback)


def format_years(years: List[int]) -> str:
    if not years:
        return "(none)"
    return ", ".join(str(y) for y in sorted(years))


def ai_analysis_summary(
    df_filtered: pd.DataFrame,
    value_col: str,
    txn_bucket: str,
    product: str,
    years: List[int],
) -> str:
    if df_filtered.empty:
        return "No data available for the current filters."

    total_value = df_filtered[value_col].sum()
    total_rows = len(df_filtered)

    by_year = df_filtered.groupby("year")[value_col].sum().sort_index()
    top_year = by_year.idxmax() if not by_year.empty else None
    yoy_trend = ""
    if len(by_year) >= 2:
        first_year = by_year.index[0]
        last_year = by_year.index[-1]
        if by_year.loc[last_year] > by_year.loc[first_year]:
            yoy_trend = "Overall trend is up from the earliest to latest year."
        elif by_year.loc[last_year] < by_year.loc[first_year]:
            yoy_trend = "Overall trend is down from the earliest to latest year."
        else:
            yoy_trend = "Overall trend is flat across the selected years."

    return (
        f"Bucket: {txn_bucket}. Product: {product}. Years: {format_years(years)}.\n"
        f"Total {human_metric_label(value_col)} = {total_value:,.2f} across {total_rows:,} transactions.\n"
        f"Top year = {top_year}.\n"
        f"{yoy_trend}"
    )


def init_slicer_state() -> None:
    if "selected_years" not in st.session_state or st.session_state.selected_years is None:
        st.session_state.selected_years = None
    if "selected_product" not in st.session_state:
        st.session_state.selected_product = "All"
    if "selected_txn_bucket" not in st.session_state:
        st.session_state.selected_txn_bucket = "Order"
    if "selected_metric" not in st.session_state:
        st.session_state.selected_metric = "Units (Quantity)"


# ----------------------------
# Load data from session
# ----------------------------
if "df_processed" not in st.session_state or st.session_state.df_processed is None:
    st.info("Upload a file on the main page first. Then return to this page.")
    st.stop()

df_base = st.session_state.df_processed.copy()
if "txn_type" not in df_base.columns:
    df_base["txn_type"] = ""
if "product_label" not in df_base.columns:
    df_base["product_label"] = ""
if "sku" not in df_base.columns:
    df_base["sku"] = df_base["product_label"].astype(str).str.strip()
df_base["date"] = pd.to_datetime(df_base["date"], errors="coerce")
df_base = df_base[df_base["date"].notna()].copy()
df_base["year"] = df_base["date"].dt.year
df_base["month"] = df_base["date"].dt.month
df_base["units"] = safe_num(df_base["quantity"]) if "quantity" in df_base.columns else 0
df_base["sales"] = safe_num(df_base["product_sales"]) if "product_sales" in df_base.columns else 0
df_base["net_proceeds"] = safe_num(df_base["total"]) if "total" in df_base.columns else 0

if "product_display" not in df_base.columns:
    sku_series = df_base["sku"].fillna("").astype(str).str.strip().replace("nan", "").replace("none", "")
    name_map = st.session_state.get("sku_product_map", {})
    name_series = sku_series.map(name_map).fillna("").astype(str).str.strip().replace("nan", "").replace("none", "")
    display_series = sku_series.where(name_series == "", name_series + " (" + sku_series + ")")
    display_series = display_series.where(display_series != "", df_base["product_label"].astype(str))
    display_series = display_series.astype(str).str.strip()
    mask_bad = display_series.str.lower().isin(("nan", "none", "")) | display_series.isna() | (display_series == "")
    display_series = display_series.where(~mask_bad, df_base["sku"].astype(str).str.strip())
    df_base["product_display"] = display_series

# ----------------------------
# Slicers (IN-DASHBOARD)
# ----------------------------
init_slicer_state()

# Available years (from valid dates)
available_years: List[int] = sorted([int(y) for y in df_base["year"].dropna().unique().tolist() if pd.notna(y)])

if not available_years:
    st.error("No valid dates found. Ensure date_time is parseable.")
    st.stop()

if st.session_state.selected_years is None:
    st.session_state.selected_years = available_years
else:
    st.session_state.selected_years = [
        y for y in st.session_state.selected_years if y in available_years
    ] or available_years

with st.container():
    st.markdown(
        "<div class='product-section-title' style='margin-top:0;margin-bottom:0.35rem;'>Filters</div>",
        unsafe_allow_html=True,
    )
    row1 = st.columns([2.6, 2.6, 1.0])

    df_skus = df_base[bucket_mask(df_base["txn_type"], st.session_state.selected_txn_bucket)].copy()
    df_skus["product_display"] = df_skus["product_display"].astype(str).str.strip()
    df_skus = df_skus[
        (df_skus["product_display"] != "")
        & (df_skus["product_display"].str.lower() != "nan")
        & (df_skus["product_display"].str.lower() != "none")
    ]
    raw_opts = sorted(df_skus["product_display"].dropna().unique().tolist())
    product_options = ["All"] + [x for x in raw_opts if x and str(x).strip().lower() not in ("nan", "none")]
    if st.session_state.selected_product not in product_options:
        st.session_state.selected_product = "All"

    with row1[0]:
        st.selectbox(
            "Product",
            options=product_options,
            key="selected_product",
        )

    with row1[1]:
        st.multiselect(
            "Year (multi-select)",
            options=available_years,
            default=st.session_state.selected_years,
            key="selected_years",
        )

    with row1[2]:
        st.write("")
        if st.button("Reset"):
            st.session_state.selected_years = available_years
            st.session_state.selected_product = "All"
            st.session_state.selected_txn_bucket = "Order"
            st.session_state.selected_metric = "Units (Quantity)"

    st.caption("These selections control the summary numbers and all charts.")

# ----------------------------
# Apply slicers
# ----------------------------
display_to_sku = (
    df_base[["sku", "product_display"]]
    .dropna()
    .drop_duplicates()
    .set_index("product_display")["sku"]
    .to_dict()
)

mask = pd.Series(True, index=df_base.index)
if st.session_state.selected_product != "All":
    selected_sku = display_to_sku.get(st.session_state.selected_product, st.session_state.selected_product)
    mask &= df_base["sku"].astype(str).str.strip() == str(selected_sku)
if st.session_state.selected_years:
    mask &= df_base["year"].isin(st.session_state.selected_years)
else:
    mask &= False

df_scope = df_base[mask].copy()
df_chart = df_scope.copy()
df_chart = df_chart[bucket_mask(df_chart["txn_type"], st.session_state.selected_txn_bucket)].copy()

st.caption(
    f"Selected: {st.session_state.selected_txn_bucket} | "
    f"Product = {sanitize_display(st.session_state.selected_product, 'All')} | "
    f"Years = {format_years(st.session_state.selected_years)} | "
    f"Metric = {st.session_state.selected_metric}"
)

if df_scope.empty:
    st.warning("No data for selected Product/Year selection.")
    st.stop()

if df_chart.empty:
    st.warning("No data matches the current chart filters. Please select another product.")
    st.stop()

# ----------------------------
# KPIs (business KPIs)
# ----------------------------
kpis = compute_kpis(df_scope)

sku_label = (
    sanitize_display(st.session_state.selected_product, "All Products")
    if st.session_state.selected_product != "All" and not _is_placeholder(st.session_state.selected_product)
    else "All Products"
)
years_label_kpi = (
    ", ".join(str(int(y)) for y in st.session_state.selected_years if pd.notna(y))
    if st.session_state.selected_years
    else "(none)"
)

total_amazon_fees = float(kpis["net_sales"] - kpis["net_proceeds"])
sales_series = safe_num(df_scope["product_sales"]) if "product_sales" in df_scope.columns else pd.Series(0, index=df_scope.index)
txn_series = df_scope.get("txn_type", pd.Series([""] * len(df_scope), index=df_scope.index)).astype(str)
is_order = bucket_mask(txn_series, "Order")
is_refund = bucket_mask(txn_series, "Refund")
sales_order = float(sales_series[is_order].sum())
sales_refund = float(sales_series[is_refund].sum())
sales_refund_abs = abs(sales_refund)
net_sales_value = float(sales_order - sales_refund_abs)
return_rate = (kpis["units_returned"] / kpis["units_sold"]) if kpis["units_sold"] else 0

st.markdown("<h2 class='product-section-title'>Key Performance Indicators</h2>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown(
        '<div data-product-tile="kpi" style="display:none;width:0;height:0;position:absolute;" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    if st.session_state.selected_product == "All" or _is_placeholder(st.session_state.selected_product):
        st.markdown(
            f"<div style='width:100%;'>"
            f"<div style='text-align:center; font-size:1.55em; font-weight:700; color:#111827;'>All Products</div>"
            f"<div style='text-align:center; font-size:1.35em; color:#4b5563;'>Years: {years_label_kpi}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        prod_header = sanitize_display(st.session_state.selected_product, "All Products")
        st.markdown(
            f"<div style='width:100%;'>"
            f"<div style='text-align:center; font-size:1.35em; font-weight:700; overflow-x:auto; color:#111827;'>"
            f"<span style='white-space:nowrap;'>Product: {prod_header}</span></div>"
            f"<div style='text-align:center; font-size:1.35em; color:#4b5563;'>Years: {years_label_kpi}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<hr style='border:0; border-top:1px solid #E2E8F0; margin:12px 0 16px 0;'>",
        unsafe_allow_html=True,
    )

    _tip_net_units = (
        "Net Units Sold = Units Sold minus Units Returned. "
        "The dollar amount in parentheses is net order sales (order sales minus refund amounts)."
    )
    _tip_fees = (
        "Total Amazon Fees is estimated as Net Sales minus Net Proceeds "
        "(FBA, referral, and other marketplace fees reflected in settlements)."
    )
    _tip_proceeds = (
        "Net Proceeds = Net Sales minus Amazon fees (FBA, referral, etc.). "
        "Does not include product cost (COGS) or inbound freight."
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.markdown(
        "<div class='product-kpi-cell'>"
        "<div class='product-kpi-label'>"
        '<i class="fa-solid fa-bag-shopping product-kpi-icon" aria-hidden="true"></i>'
        "<span>Units Sold</span></div>"
        f"<div class='product-kpi-value'>{kpis['units_sold']:,.0f}</div>"
        f"<div class='product-kpi-sub'>(${sales_order:,.0f})</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    k2.markdown(
        "<div class='product-kpi-cell'>"
        "<div class='product-kpi-label'>"
        '<i class="fa-solid fa-arrow-rotate-left product-kpi-icon" aria-hidden="true"></i>'
        "<span>Units Returned | Return Rate</span></div>"
        f"<div class='product-kpi-value'>{kpis['units_returned']:,.0f} | {return_rate:.1%}</div>"
        f"<div class='product-kpi-sub'>(-${sales_refund_abs:,.0f})</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    k3.markdown(
        "<div class='product-kpi-cell'>"
        "<div class='product-kpi-label'>"
        '<i class="fa-solid fa-cubes product-kpi-icon" aria-hidden="true"></i>'
        "<span>Net Units Sold</span>"
        f"{_kpi_info_tooltip(_tip_net_units)}</div>"
        f"<div class='product-kpi-value'>{kpis['net_units']:,.0f}</div>"
        f"<div class='product-kpi-sub'>(${net_sales_value:,.0f})</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    k4.markdown(
        "<div class='product-kpi-cell'>"
        "<div class='product-kpi-label'>"
        '<i class="fa-solid fa-file-invoice-dollar product-kpi-icon" aria-hidden="true"></i>'
        "<span>Total Amazon Fees ($)</span>"
        f"{_kpi_info_tooltip(_tip_fees)}</div>"
        f"<div class='product-kpi-value'>${total_amazon_fees:,.0f}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    k5.markdown(
        "<div class='product-kpi-cell'>"
        "<div class='product-kpi-label'>"
        '<i class="fa-solid fa-wallet product-kpi-icon" aria-hidden="true"></i>'
        "<span>Net Proceeds ($)</span>"
        f"{_kpi_info_tooltip(_tip_proceeds)}</div>"
        f"<div class='product-kpi-value'>${kpis['net_proceeds']:,.0f}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

with st.container():
    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
    st.markdown("<h2 class='product-section-title'>What Do You Want to Analyze?</h2>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:1.125em; line-height:1.5; color:#4b5563;'>These options change the charts below.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

    row2 = st.columns([2.4, 2.4])

    bucket_options = ["Order", "Refund", "Liquidations", "Adjustment"]
    if st.session_state.selected_txn_bucket not in bucket_options:
        st.session_state.selected_txn_bucket = "Order"

    with row2[0]:
        st.markdown(
            "<div style='font-size:1.25em; font-weight:600; color:#0f766e;'>Transaction Bucket</div>",
            unsafe_allow_html=True,
        )
        st.radio(
            "Transaction Bucket",
            options=bucket_options,
            horizontal=True,
            key="selected_txn_bucket",
            label_visibility="collapsed",
        )

    with row2[1]:
        st.markdown(
            "<div style='font-size:1.25em; font-weight:600; color:#0f766e;'>Metric</div>",
            unsafe_allow_html=True,
        )
        metric_options = ["Units (Quantity)", "Sales ($)", "Net Proceeds ($)"]
        if st.session_state.selected_metric not in metric_options:
            st.session_state.selected_metric = "Units (Quantity)"
        st.radio(
            "Metric",
            options=metric_options,
            horizontal=False,
            key="selected_metric",
            label_visibility="collapsed",
        )

metric_value_map = {
    "Units (Quantity)": "units",
    "Sales ($)": "sales",
    "Net Proceeds ($)": "net_proceeds",
}
value_col = metric_value_map.get(st.session_state.selected_metric, "units")
metric_label = human_metric_label(value_col)
chart_title_metric_line = chart_title_metric_phrase(
    st.session_state.selected_txn_bucket,
    st.session_state.selected_metric,
    metric_label,
)
years_label = format_years(st.session_state.selected_years or [])

_pie_bar_top = "Annual Comparison"

if value_col == "net_proceeds":
    m_transfer = transfer_mask(df_chart)
    df_chart_effective = df_chart.loc[~m_transfer].copy()
else:
    df_chart_effective = df_chart

df_year = df_chart_effective.groupby("year", as_index=False)[value_col].sum()
df_year["year"] = df_year["year"].astype(int)
_years_sorted = sorted(df_year["year"].unique().tolist())
_max_chart_year = max(_years_sorted) if _years_sorted else None
year_color_map = (
    {y: brand_color_for_year(int(y), int(_max_chart_year)) for y in _years_sorted}
    if _max_chart_year is not None
    else {}
)
# Bar charts: color must be categorical strings — integer year triggers a continuous bluescale + bad axis
year_color_map_str = {str(y): year_color_map[y] for y in _years_sorted}

fig_pie = px.pie(
    df_year,
    values=value_col,
    names="year",
    color="year",
    color_discrete_map=year_color_map,
)
fig_pie.update_layout(
    title=_plotly_three_line_centered_title(_pie_bar_top, sku_label, chart_title_metric_line),
    margin=dict(t=178),
    font=dict(size=CHART_TICK_PT),
    legend=dict(font=dict(size=CHART_LEGEND_PT)),
)
fig_pie.update_traces(textfont=dict(size=CHART_PIE_TEXT_PT))

if st.session_state.selected_product != "All":
    df_bar = df_chart_effective.groupby("year", as_index=False)[value_col].sum()
    df_bar["year"] = df_bar["year"].astype(int)
    # Categorical y so Plotly does not treat year as continuous (no 2023.5 / 2,024.5 ticks)
    df_bar["year_label"] = df_bar["year"].astype(str)
    fig_bar = px.bar(
        df_bar,
        x=value_col,
        y="year_label",
        orientation="h",
        text=value_col,
        color="year_label",
        color_discrete_map=year_color_map_str,
        labels={"year_label": "Year", value_col: metric_label},
    )
    fig_bar.update_traces(
        texttemplate="%{text:.2s}",
        textposition="outside",
        textfont=dict(size=CHART_BAR_TEXT_PT),
    )
    fig_bar.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(t=178))
    _years_cat = [str(y) for y in sorted(df_bar["year"].unique())]
    fig_bar.update_yaxes(type="category", categoryorder="array", categoryarray=_years_cat)
else:
    # All products: one bar per year (totals only), same colors as line & pie — no product breakdown
    df_bar = df_year.copy()
    df_bar["year_label"] = df_bar["year"].astype(str)
    fig_bar = px.bar(
        df_bar,
        x="year_label",
        y=value_col,
        color="year_label",
        color_discrete_map=year_color_map_str,
        labels={"year_label": "Year", value_col: metric_label},
    )
    fig_bar.update_traces(textfont=dict(size=CHART_BAR_TEXT_PT))
    fig_bar.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(t=178))
    _x_order = [str(y) for y in _years_sorted]
    fig_bar.update_xaxes(type="category", categoryorder="array", categoryarray=_x_order)

fig_bar.update_layout(
    title=_plotly_three_line_centered_title(_pie_bar_top, sku_label, chart_title_metric_line),
    font=dict(size=CHART_TICK_PT),
)
fig_bar.update_xaxes(
    title_font=dict(size=CHART_AXIS_TITLE_PT),
    tickfont=dict(size=CHART_TICK_PT),
)
fig_bar.update_yaxes(
    title_font=dict(size=CHART_AXIS_TITLE_PT),
    tickfont=dict(size=CHART_TICK_PT),
)

# ----------------------------
# YoY overlay chart (Jan–Dec, line per year)
# ----------------------------
value_label = metric_label
df_yoy = (
    df_chart_effective
    .dropna(subset=["year", "month"])
    .groupby(["month", "year"], as_index=False)[value_col]
    .sum()
)

df_yoy["month"] = df_yoy["month"].astype(int)
df_yoy["year"] = df_yoy["year"].astype(int)

fig_yoy = px.line(
    df_yoy,
    x="month",
    y=value_col,
    color="year",
    color_discrete_map=year_color_map,
    markers=True,
    labels={"month": "Month", value_col: value_label, "year": "Year"},
)

fig_yoy.update_xaxes(
    tickmode="array",
    tickvals=list(range(1, 13)),
    ticktext=MONTH_ABBR,
    title_font=dict(size=CHART_AXIS_TITLE_PT),
    tickfont=dict(size=CHART_TICK_PT),
)
fig_yoy.update_yaxes(
    title_font=dict(size=CHART_AXIS_TITLE_PT),
    tickfont=dict(size=CHART_TICK_PT),
)
# Legend top-right inside plot area. YoY title is Streamlit HTML inside the YoY bordered tile — do
# not use layout.title (HTML titles can anchor inside the plot area and overlap series).
fig_yoy.update_layout(
    title=None,
    height=CHART_YOY_HEIGHT_PX,
    font=dict(size=CHART_TICK_PT),
    legend=dict(
        orientation="h",
        yanchor="top",
        y=0.94,
        xanchor="right",
        x=0.99,
        font=dict(size=CHART_LEGEND_PT),
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="#E2E8F0",
        borderwidth=1,
    ),
    margin=dict(l=72, r=56, t=56, b=64),
)

# Monthly trend full width; bar (left) and pie (right) on one row
st.markdown("<h2 class='product-section-title'>Visualizations</h2>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown(
        '<div data-product-tile="viz" style="display:none;width:0;height:0;position:absolute;" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        # One markdown block: marker + visible title (avoids a lone hidden block that can show "undefined")
        st.markdown(
            "<div data-chart-tile='yoy' class='product-yoy-chart-block'>"
            "<div class='product-yoy-chart-heading'>"
            + _three_line_chart_title_html(
                "Monthly Trend (YoY)",
                sku_label,
                chart_title_metric_line,
            )
            + "</div></div>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig_yoy, use_container_width=True, key="product_perf_yoy_chart")
    _bar_col, _pie_col = st.columns([1.35, 1.0], gap="large")
    with _bar_col:
        with st.container(border=True):
            st.markdown(
                '<div data-chart-tile="bar" style="display:none;width:0;height:0;position:absolute;" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(fig_bar, use_container_width=True)
    with _pie_col:
        with st.container(border=True):
            st.markdown(
                '<div data-chart-tile="pie" style="display:none;width:0;height:0;position:absolute;" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

analysis_text = ai_analysis_summary(
    df_chart_effective,
    value_col,
    st.session_state.selected_txn_bucket,
    st.session_state.selected_product,
    st.session_state.selected_years or [],
)
st.markdown("<h2 class='product-section-title'>AI Analysis (Auto Summary)</h2>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown(
        '<div data-product-tile="ai" style="display:none;width:0;height:0;position:absolute;" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.info(analysis_text)
    st.caption(
        "ℹ️ Net Proceeds ($) represents the final amount Amazon credits or debits after "
        "marketplace fees, refunds, and adjustments. It does not include product cost "
        "(COGS) or inbound shipping expenses. To estimate true profit, you must subtract "
        "COGS and freight/shipping costs separately."
    )

with st.expander("View filtered data (debug)"):
    st.dataframe(
        df_chart[
            ["date", "txn_type", "product_display", "sku", "units", "sales", "net_proceeds", "year", "month"]
        ].sort_values("date"),
        use_container_width=True,
        hide_index=True,
    )
