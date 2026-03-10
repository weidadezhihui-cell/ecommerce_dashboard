"""
Amazon Settlement - Analysis by Product
PowerBI-style in-dashboard slicers + YoY overlay charts (Jan–Dec, line per year)
"""

from __future__ import annotations

import calendar
from typing import Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import to_money

# ----------------------------
# Page config / title (styles aligned with Key Performance Indicator page)
# ----------------------------
st.set_page_config(page_title="Product Performance", layout="wide")
st.markdown(
    """
    <style>
    .kpi-page-title { font-size: 2.75rem !important; font-weight: 700; color: #1f2937; margin-bottom: 0.5rem; }
    .product-page-subtitle { font-size: 1.25rem !important; color: #6b7280; margin-bottom: 1rem; }
    .product-section-title { font-size: 1.75rem !important; font-weight: 700; color: #1f2937; margin-top: 1rem; margin-bottom: 0.5rem; }
    [data-testid="stSelectbox"] label, [data-testid="stSelectbox"] [data-testid="stWidgetLabel"], [data-testid="stSelectbox"] [data-testid="stWidgetLabel"] p,
    [data-testid="stMultiSelect"] label, [data-testid="stMultiSelect"] [data-testid="stWidgetLabel"], [data-testid="stMultiSelect"] [data-testid="stWidgetLabel"] p { font-size: 1.5rem !important; font-weight: 600 !important; line-height: 1.4 !important; }
    [data-testid="stSelectbox"], [data-testid="stMultiSelect"] { width: 100% !important; max-width: 100% !important; min-width: 0 !important; margin-top: 0 !important; margin-bottom: 0 !important; }
    [data-testid="stSelectbox"] label + div, [data-testid="stMultiSelect"] > div, [data-testid="stMultiSelect"] > div > div { width: 100% !important; min-height: 3.25rem !important; padding: 0.5rem 0.75rem !important; box-sizing: border-box !important; }
    [data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input, [data-testid="stMultiSelect"] [data-testid="stWidgetValue"] { font-size: 1.25rem !important; }
    [data-testid="stCaptionContainer"] { font-size: 1.25rem !important; }
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
    st.markdown("<div class='product-section-title' style='margin-top:0;'>Filters</div>", unsafe_allow_html=True)
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

st.markdown("<h2 class='product-section-title'>Key Performance Indicators</h2>", unsafe_allow_html=True)
if st.session_state.selected_product == "All" or _is_placeholder(st.session_state.selected_product):
    st.markdown(
        f"<div style='width:100%;'>"
        f"<div style='text-align:center; font-size:1.4em; font-weight:700;'>All Products</div>"
        f"<div style='text-align:center; font-size:1.2em;'>Years: {years_label_kpi}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
else:
    prod_header = sanitize_display(st.session_state.selected_product, "All Products")
    st.markdown(
        f"<div style='width:100%;'>"
        f"<div style='text-align:center; font-size:1.2em; font-weight:700; overflow-x:auto;'>"
        f"<span style='white-space:nowrap;'>Product: {prod_header}</span></div>"
        f"<div style='text-align:center; font-size:1.2em;'>Years: {years_label_kpi}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("<hr style='border:0; border-top:2px solid #0f766e; margin:10px 0 14px 0;'>", unsafe_allow_html=True)
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

k1, k2, k3, k4, k5 = st.columns(5)
k1.markdown(
    f"<div style='text-align:center; font-size:1.05em; font-weight:600; color:#0f766e;'>Units Sold</div>"
    f"<div style='text-align:center; font-size:1.6em; font-weight:700;'>{kpis['units_sold']:,.0f}</div>"
    f"<div style='text-align:center; font-size:1.2em;'>(${sales_order:,.0f})</div>",
    unsafe_allow_html=True,
)
k2.markdown(
    f"<div style='text-align:center; font-size:1.05em; font-weight:600; color:#0f766e;'>Units Returned | Return Rate</div>"
    f"<div style='text-align:center; font-size:1.6em; font-weight:700;'>{kpis['units_returned']:,.0f} | {return_rate:.1%}</div>"
    f"<div style='text-align:center; font-size:1.2em;'>(-${sales_refund_abs:,.0f})</div>",
    unsafe_allow_html=True,
)
k3.markdown(
    f"<div style='text-align:center; font-size:1.05em; font-weight:600; color:#0f766e;'>Net Units Sold</div>"
    f"<div style='text-align:center; font-size:1.6em; font-weight:700;'>{kpis['net_units']:,.0f}</div>"
    f"<div style='text-align:center; font-size:1.2em;'>(${net_sales_value:,.0f})</div>",
    unsafe_allow_html=True,
)
k4.markdown(
    f"<div style='text-align:center; font-size:1.05em; font-weight:600; color:#0f766e;'>Total Amazon Fees ($)</div>"
    f"<div style='text-align:center; font-size:1.6em; font-weight:700;'>${total_amazon_fees:,.0f}</div>",
    unsafe_allow_html=True,
)
k5.markdown(
    f"<div style='text-align:center; font-size:1.05em; font-weight:600; color:#0f766e;'>Net Proceeds ($)</div>"
    f"<div style='text-align:center; font-size:1.6em; font-weight:700;'>${kpis['net_proceeds']:,.0f}</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<br>"
    "<div style='font-size:1.05em;'>"
    "Note:<br>"
    "Net Units Sold = Units Sold \u2212 Units Returned.<br>"
    "Amounts in parentheses ($) show the related sales or refund value.<br>"
    "Net Proceeds = Net Sales \u2212 Amazon fees (FBA, referral, etc.)."
    "</div>",
    unsafe_allow_html=True,
)

with st.container():
    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
    st.markdown("<h2 class='product-section-title'>What Do You Want to Analyze?</h2>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:1.05em;'>These options change the charts below.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

    row2 = st.columns([2.4, 2.4])

    bucket_options = ["Order", "Refund", "Liquidations", "Adjustment"]
    if st.session_state.selected_txn_bucket not in bucket_options:
        st.session_state.selected_txn_bucket = "Order"

    with row2[0]:
        st.markdown(
            "<div style='font-size:1.1em; font-weight:600; color:#0f766e;'>Transaction Bucket</div>",
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
            "<div style='font-size:1.1em; font-weight:600; color:#0f766e;'>Metric</div>",
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

st.markdown("<h2 class='product-section-title'>Visualizations</h2>", unsafe_allow_html=True)

metric_value_map = {
    "Units (Quantity)": "units",
    "Sales ($)": "sales",
    "Net Proceeds ($)": "net_proceeds",
}
value_col = metric_value_map.get(st.session_state.selected_metric, "units")
metric_label = human_metric_label(value_col)
years_label = format_years(st.session_state.selected_years or [])

pie_title = f"{st.session_state.selected_txn_bucket} • {metric_label} by Year"

if value_col == "net_proceeds":
    m_transfer = transfer_mask(df_chart)
    df_chart_effective = df_chart.loc[~m_transfer].copy()
else:
    df_chart_effective = df_chart

df_year = df_chart_effective.groupby("year", as_index=False)[value_col].sum()
fig_pie = px.pie(
    df_year,
    values=value_col,
    names="year",
    title=pie_title,
)

if st.session_state.selected_product != "All":
    bar_title = f"{st.session_state.selected_txn_bucket} • {metric_label} by Year"
    df_bar = df_chart_effective.groupby("year", as_index=False)[value_col].sum()
    fig_bar = px.bar(
        df_bar,
        x=value_col,
        y="year",
        orientation="h",
        text=value_col,
        title=bar_title,
        labels={"year": "Year", value_col: metric_label},
    )
    fig_bar.update_traces(texttemplate="%{text:.2s}", textposition="outside")
else:
    bar_title = f"{st.session_state.selected_txn_bucket} • {metric_label} by Product"
    top_n = 8
    df_prod = df_chart_effective.groupby("product_display", as_index=False)[value_col].sum()
    top_products = df_prod.sort_values(value_col, ascending=False).head(top_n)["product_display"].tolist()
    df_chart_effective["product_group"] = df_chart_effective["product_display"].where(
        df_chart_effective["product_display"].isin(top_products), "Other"
    )
    df_stack = df_chart_effective.groupby(["year", "product_group"], as_index=False)[value_col].sum()
    fig_bar = px.bar(
        df_stack,
        x="year",
        y=value_col,
        color="product_group",
        title=bar_title,
        labels={"year": "Year", value_col: metric_label, "product_group": "Product"},
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

chart_title = f"Monthly Trend (YoY) • {metric_label}"

fig_yoy = px.line(
    df_yoy,
    x="month",
    y=value_col,
    color="year",
    markers=True,
    title=chart_title,
    labels={"month": "Month", value_col: value_label, "year": "Year"},
)

fig_yoy.update_xaxes(
    tickmode="array",
    tickvals=list(range(1, 13)),
    ticktext=MONTH_ABBR,
)

left_col, right_col = st.columns([2.2, 1.0])
with left_col:
    st.plotly_chart(fig_yoy, use_container_width=True)
with right_col:
    st.plotly_chart(fig_pie, use_container_width=True)
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("<h2 class='product-section-title'>AI Analysis (Auto Summary)</h2>", unsafe_allow_html=True)
analysis_text = ai_analysis_summary(
    df_chart_effective,
    value_col,
    st.session_state.selected_txn_bucket,
    st.session_state.selected_product,
    st.session_state.selected_years or [],
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
