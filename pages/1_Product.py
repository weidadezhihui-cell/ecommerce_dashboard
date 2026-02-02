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

# ----------------------------
# Page config / title
# ----------------------------
st.set_page_config(page_title="Product Performance", layout="wide")
st.markdown("# Product Performance")
st.caption("Amazon Settlement · Compare transaction trends across years (Jan–Dec overlay)")

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
    return pd.to_numeric(s, errors="coerce").fillna(0)


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

    units_sold = float(df.loc[m_order, "quantity"].sum())
    units_returned = float(df.loc[m_refund, "quantity"].sum())
    net_units = units_sold - units_returned

    sales_order = float(df.loc[m_order, "product_sales"].sum())
    sales_refund = float(df.loc[m_refund, "product_sales"].sum())
    net_sales = sales_order - sales_refund

    net_proceeds = float(df["total"].sum())
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
    sku_series = df_base["sku"].fillna("").astype(str).str.strip()
    name_map = st.session_state.get("sku_product_map", {})
    name_series = sku_series.map(name_map).fillna("").astype(str).str.strip()
    display_series = sku_series.where(name_series == "", name_series + " (" + sku_series + ")")
    display_series = display_series.where(display_series != "", df_base["product_label"].astype(str))
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
    st.markdown("**Filters**")
    row1 = st.columns([2.6, 2.6, 1.0])

    df_skus = df_base[bucket_mask(df_base["txn_type"], st.session_state.selected_txn_bucket)].copy()
    df_skus["product_display"] = df_skus["product_display"].astype(str).str.strip()
    df_skus = df_skus[df_skus["product_display"] != ""]
    product_options = ["All"] + sorted(df_skus["product_display"].unique().tolist())
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
    f"Product = {st.session_state.selected_product} | "
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

sku_label = st.session_state.selected_product if st.session_state.selected_product != "All" else "All Products"
years_label_kpi = (
    ", ".join(str(y) for y in st.session_state.selected_years)
    if st.session_state.selected_years
    else "(none)"
)

st.markdown("## Key Performance Indicators")
if st.session_state.selected_product == "All":
    st.markdown(f"**All Products | Years: {years_label_kpi}**")
else:
    st.markdown(f"**Product: {st.session_state.selected_product} | Years: {years_label_kpi}**")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Units Sold", f"{kpis['units_sold']:,.0f}")
k2.metric("Units Returned", f"{kpis['units_returned']:,.0f}")
k3.metric("Net Units", f"{kpis['net_units']:,.0f}")
k4.metric("Net Sales ($)", f"${kpis['net_sales']:,.0f}")
k5.metric("Net Proceeds ($)", f"${kpis['net_proceeds']:,.0f}")
st.caption(
    "Units Sold/Returned reflect product movement. Net Sales shows revenue minus refunds. "
    "Net Proceeds is Amazon payout impact."
)

with st.container():
    st.markdown("### What Do You Want to Analyze?")
    st.caption("These options change the charts below.")

    row2 = st.columns([2.4, 2.4])

    bucket_options = ["Order", "Refund", "Liquidations", "Adjustment"]
    if st.session_state.selected_txn_bucket not in bucket_options:
        st.session_state.selected_txn_bucket = "Order"

    with row2[0]:
        st.radio(
            "Transaction Bucket",
            options=bucket_options,
            horizontal=True,
            key="selected_txn_bucket",
        )

    with row2[1]:
        metric_options = ["Units (Quantity)", "Sales ($)", "Net Proceeds ($)"]
        if st.session_state.selected_metric not in metric_options:
            st.session_state.selected_metric = "Units (Quantity)"
        st.radio(
            "Metric",
            options=metric_options,
            horizontal=False,
            key="selected_metric",
        )

st.markdown("### Visualizations")

metric_value_map = {
    "Units (Quantity)": "units",
    "Sales ($)": "sales",
    "Net Proceeds ($)": "net_proceeds",
}
value_col = metric_value_map.get(st.session_state.selected_metric, "units")
metric_label = human_metric_label(value_col)
years_label = format_years(st.session_state.selected_years or [])

pie_title = f"{st.session_state.selected_txn_bucket} • {metric_label} by Year"

df_year = df_chart.groupby("year", as_index=False)[value_col].sum()
fig_pie = px.pie(
    df_year,
    values=value_col,
    names="year",
    title=pie_title,
)

if st.session_state.selected_product != "All":
    bar_title = f"{st.session_state.selected_txn_bucket} • {metric_label} by Year"
    df_bar = df_chart.groupby("year", as_index=False)[value_col].sum()
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
    df_prod = df_chart.groupby("product_display", as_index=False)[value_col].sum()
    top_products = df_prod.sort_values(value_col, ascending=False).head(top_n)["product_display"].tolist()
    df_chart["product_group"] = df_chart["product_display"].where(
        df_chart["product_display"].isin(top_products), "Other"
    )
    df_stack = df_chart.groupby(["year", "product_group"], as_index=False)[value_col].sum()
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
    df_chart
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

st.markdown("### AI Analysis (Auto Summary)")
analysis_text = ai_analysis_summary(
    df_chart,
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
