"""
Streamlit E-commerce Analytics Dashboard MVP
Main application file with file upload, filters, KPIs, charts, and AI analysis.
"""

from typing import Tuple, Dict

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from utils import (
    load_data,
    normalize_columns,
    compute_metrics,
    generate_sample_data,
    CANONICAL_COLUMNS,
)

load_dotenv()

st.set_page_config(
    page_title="E-commerce Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 E-commerce Analytics Dashboard")
st.markdown("Upload your sales data or explore with sample data")

if "df" not in st.session_state:
    st.session_state.df = None
if "df_processed" not in st.session_state:
    st.session_state.df_processed = None
if "summary" not in st.session_state:
    st.session_state.summary = None
if "product_name_map" not in st.session_state:
    st.session_state.product_name_map = {}
if "product_name_map_skus" not in st.session_state:
    st.session_state.product_name_map_skus = []


DEBUG = False


def _debug_log(location: str, message: str, data: Dict, hypothesis_id: str, run_id: str = "pre-fix") -> None:
    if not DEBUG:
        return
    # #region agent log
    try:
        import json, time
        with open(
            r"c:\Users\Mark.Zhao\OneDrive - Government of Alberta\Documents\ecommerce_dashboard\.cursor\debug.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": run_id,
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data,
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion


def is_amazon_mode(df_normalized: pd.DataFrame) -> bool:
    """Amazon mode when canonical columns include date_time, txn_type, total."""
    columns = set(df_normalized.columns)
    return "date_time" in columns and "total" in columns and ("txn_type" in columns or "type" in columns)


def validate_required_columns(
    df_normalized: pd.DataFrame, is_amazon: bool
) -> Tuple[bool, list, list]:
    """Validate required columns for Amazon or generic mode."""
    detected = list(df_normalized.columns)
    if is_amazon:
        required = ["date_time", "total"]
        missing = [col for col in required if col not in detected]
        if "txn_type" not in detected and "type" not in detected:
            missing.extend(["txn_type", "type"])
    else:
        required = ["date", "revenue"]
        missing = [col for col in required if col not in detected]
    return len(missing) == 0, missing, detected


def build_amazon_computed_fields(df_normalized: pd.DataFrame) -> pd.DataFrame:
    """Build Amazon settlement computed fields."""
    df = df_normalized.copy()
    _debug_log(
        "app.py:52",
        "build_amazon_computed_fields:entry",
        {"columns": list(df.columns)},
        "H1",
    )

    df["date"] = pd.to_datetime(df["date_time"], errors="coerce") if "date_time" in df.columns else pd.NaT
    if "txn_type" in df.columns:
        df["txn_type"] = df["txn_type"].astype(str)
    elif "type" in df.columns:
        df["txn_type"] = df["type"].astype(str)
    else:
        df["txn_type"] = ""
    df["net_proceeds"] = pd.to_numeric(df.get("total", 0), errors="coerce").fillna(0)

    if "product_sales" in df.columns:
        df["gross_sales"] = pd.to_numeric(df["product_sales"], errors="coerce").fillna(0)
    else:
        df["gross_sales"] = 0

    fee_cols = [
        "selling_fees",
        "fba_fees",
        "other_transaction_fees",
        "other",
        "regulatory_fee",
        "tax_on_regulatory_fee",
        "service_fee",
    ]
    df["fees_total"] = 0
    for col in fee_cols:
        if col in df.columns:
            df["fees_total"] += pd.to_numeric(df[col], errors="coerce").fillna(0)
    _debug_log(
        "app.py:79",
        "build_amazon_computed_fields:fees_total",
        {"fee_cols_present": [c for c in fee_cols if c in df.columns], "fees_total_sum": float(df["fees_total"].sum())},
        "H2",
    )

    if "order_state" in df.columns:
        df["location"] = df["order_state"]
    elif "location" not in df.columns:
        df["location"] = None

    if "sku" in df.columns:
        df["product_label"] = df["sku"]
    elif "description" in df.columns:
        df["product_label"] = df["description"]
    else:
        df["product_label"] = "(unknown)"

    return df


def compute_amazon_metrics(df: pd.DataFrame) -> Dict:
    """Compute summary metrics for Amazon settlement data."""
    order_count = len(df[df["txn_type"].str.contains("Order", case=False, na=False)]) if "txn_type" in df.columns else 0
    refund_count = len(df[df["txn_type"].str.contains("Refund", case=False, na=False)]) if "txn_type" in df.columns else 0

    return {
        "total_net_proceeds": df["net_proceeds"].sum() if "net_proceeds" in df.columns else 0,
        "total_gross_sales": df["gross_sales"].sum() if "gross_sales" in df.columns else 0,
        "total_fees": df["fees_total"].sum() if "fees_total" in df.columns else 0,
        "order_count": order_count,
        "refund_count": refund_count,
        "total_transactions": len(df),
    }


def simulate_ai_analysis(df: pd.DataFrame, summary: Dict, mode: str = "generic") -> str:
    """Simulate an AI analysis report (placeholder for future OpenAI integration)."""
    if mode == "amazon":
        top_product = None
        if "product_display" in df.columns and not df.empty:
            top_product = (
                df.groupby("product_display")["net_proceeds"].sum().sort_values(ascending=False).head(1).index[0]
            )
        return f"""
# AI Analysis Report (Amazon Settlement)

## Executive Summary
Based on {summary.get('total_transactions', 0)} transactions:

- **Net Proceeds ($)**: ${summary.get('total_net_proceeds', 0):,.2f}
- **Total Gross Sales**: ${summary.get('total_gross_sales', 0):,.2f}
- **Total Fees**: ${summary.get('total_fees', 0):,.2f}
- **Orders / Refunds**: {summary.get('order_count', 0)} / {summary.get('refund_count', 0)}

## Key Insights
- Fee impact is visible in net proceeds vs gross sales.
- Refund activity influences net proceeds trends.
- State performance helps prioritize logistics and marketing.
{f"- Top product by net proceeds: **{top_product}**" if top_product else ""}

## Recommendations
- Review high-fee transactions for optimization opportunities.
- Monitor refund-heavy SKUs and investigate root causes.
- Focus on top-performing states and products.

---
*Note: This is a simulated analysis. Connect OpenAI API for real AI-powered insights.*
"""

    return f"""
# AI Analysis Report

## Executive Summary
Based on the analysis of {len(df)} transactions:

- **Total Revenue**: ${summary.get('total_revenue', 0):,.2f}
- **Total Net Profit**: ${summary.get('total_net_profit', 0):,.2f}
- **Average Margin**: {summary.get('avg_margin_pct', 0):.2f}%

## Key Insights
- Profitability trends depend on product mix and costs.
- Top SKUs are key drivers of net profit.
- Location performance varies across regions.

## Recommendations
- Focus marketing on high-margin products.
- Optimize ad spend by region.
- Review cost structure to improve margins.

---
*Note: This is a simulated analysis. Connect OpenAI API for real AI-powered insights.*
"""


def render_amazon_dashboard(df: pd.DataFrame, summary: Dict) -> None:
    """Render the Amazon settlement dashboard."""
    st.header("📈 Key Performance Indicators")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Net Proceeds ($)", f"${summary['total_net_proceeds']:,.2f}")
    with col2:
        st.metric("Total Gross Sales", f"${summary['total_gross_sales']:,.2f}")
    with col3:
        st.metric("Total Fees", f"${summary['total_fees']:,.2f}")
    with col4:
        st.metric("Orders", summary["order_count"])
    with col5:
        st.metric("Refunds", summary["refund_count"])

    st.header("📊 Visualizations")

    if "date" in df.columns and df["date"].notna().any():
        df_month = df.copy()
        df_month["month"] = df_month["date"].dt.to_period("M").dt.to_timestamp()
        df_month = df_month.groupby("month", as_index=False)["net_proceeds"].sum()

        fig_month = px.line(
            df_month,
            x="month",
            y="net_proceeds",
            title="Monthly Net Proceeds",
            labels={"month": "Month", "net_proceeds": "Net Proceeds ($)"},
        )
        st.plotly_chart(fig_month, use_container_width=True)

    fee_cols = [
        c
        for c in [
            "selling_fees",
            "fba_fees",
            "other_transaction_fees",
            "other",
            "regulatory_fee",
            "tax_on_regulatory_fee",
            "service_fee",
        ]
        if c in df.columns
    ]
    _debug_log(
        "app.py:142",
        "render_amazon_dashboard:fee_cols",
        {"fee_cols": fee_cols},
        "H3",
    )
    if fee_cols:
        fee_data = df[fee_cols].sum().reset_index()
        fee_data.columns = ["Fee Type", "Amount"]
        fig_fees = px.pie(
            fee_data,
            values="Amount",
            names="Fee Type",
            title="Fee Breakdown",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        st.plotly_chart(fig_fees, use_container_width=True)

    if "location" in df.columns and df["location"].notna().any():
        df_state = df.groupby("location", as_index=False)["net_proceeds"].sum()
        df_state = df_state.sort_values("net_proceeds", ascending=False)
        fig_state = px.bar(
            df_state,
            x="location",
            y="net_proceeds",
            title="Net Proceeds by State",
            labels={"location": "State", "net_proceeds": "Net Proceeds ($)"},
            color="net_proceeds",
            color_continuous_scale="Viridis",
        )
        fig_state.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_state, use_container_width=True)

    st.header("🏆 Top Products")
    display_col = "product_display" if "product_display" in df.columns else "product_label"
    if display_col in df.columns:
        df_products = df.groupby(display_col, as_index=False).agg(
            gross_sales=("gross_sales", "sum"),
            net_proceeds=("net_proceeds", "sum"),
            fees_total=("fees_total", "sum"),
            transactions=(display_col, "count"),
        )
        df_products = df_products.sort_values("net_proceeds", ascending=False).head(25)
        df_products = df_products.rename(columns={display_col: "Product"})
        st.dataframe(df_products, use_container_width=True, hide_index=True)
    else:
        st.info("No product labels available.")


def render_generic_dashboard(df: pd.DataFrame, summary: Dict) -> None:
    """Render the generic e-commerce dashboard."""
    st.header("📈 Key Performance Indicators")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Revenue", f"${summary['total_revenue']:,.2f}")
    with col2:
        st.metric("Total Net Profit", f"${summary['total_net_profit']:,.2f}")
    with col3:
        st.metric("Total Ad Spend", f"${summary['total_ad_spend']:,.2f}")
    with col4:
        st.metric("Avg Margin %", f"{summary['avg_margin_pct']:.2f}%")

    st.header("📊 Visualizations")
    if "date" in df.columns and df["date"].notna().any():
        df_time = df.groupby(df["date"].dt.date).agg({"revenue": "sum", "net_profit": "sum"}).reset_index()
        df_time["date"] = pd.to_datetime(df_time["date"])
        fig_time = px.line(
            df_time,
            x="date",
            y=["revenue", "net_profit"],
            title="Revenue and Net Profit Over Time",
            labels={"value": "Amount ($)", "date": "Date"},
            color_discrete_map={"revenue": "#1f77b4", "net_profit": "#2ca02c"},
        )
        st.plotly_chart(fig_time, use_container_width=True)
    else:
        st.info("Date column not available for time series chart")

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        cost_data = {
            "Category": ["COGS", "Ad Cost", "Fees"],
            "Amount": [df["cogs"].sum(), df["ad_cost"].sum(), df["fees"].sum()],
        }
        fig_costs = px.pie(
            pd.DataFrame(cost_data),
            values="Amount",
            names="Category",
            title="Cost Breakdown",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        st.plotly_chart(fig_costs, use_container_width=True)

    with col_chart2:
        if "location" in df.columns and df["location"].notna().any():
            df_location = df.groupby("location", as_index=False)["net_profit"].sum()
            df_location = df_location.sort_values("net_profit", ascending=False)
            fig_location = px.bar(
                df_location,
                x="location",
                y="net_profit",
                title="Profit by Location",
                labels={"net_profit": "Net Profit ($)", "location": "Location"},
                color="net_profit",
                color_continuous_scale="Viridis",
            )
            fig_location.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_location, use_container_width=True)
        else:
            st.info("Location column not available")

    st.header("🏆 Top 10 SKUs by Net Profit")
    if "sku" in df.columns:
        df_top_skus = df.groupby("sku", as_index=False).agg(
            net_profit=("net_profit", "sum"),
            revenue=("revenue", "sum"),
            cogs=("cogs", "sum"),
            ad_cost=("ad_cost", "sum"),
            fees=("fees", "sum"),
            margin_pct=("margin_pct", "mean"),
        )
        df_top_skus = df_top_skus.sort_values("net_profit", ascending=False).head(10)
        df_display = df_top_skus[["sku", "net_profit", "revenue", "margin_pct"]].copy()
        df_display.columns = ["SKU", "Net Profit ($)", "Revenue ($)", "Avg Margin (%)"]
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("SKU column not available")


st.sidebar.header("📁 Data Upload")
uploaded_file = st.sidebar.file_uploader(
    "Upload CSV or XLSX file",
    type=["csv", "xlsx", "xls"],
    help="Upload your e-commerce data file",
)

if uploaded_file is not None:
    try:
        df_raw = load_data(uploaded_file)
        if df_raw is not None and not df_raw.empty:
            st.sidebar.success(f"✅ File loaded: {uploaded_file.name} ({len(df_raw)} rows)")
            st.session_state.df = df_raw
    except Exception as e:
        st.sidebar.error(f"❌ Error loading file: {str(e)}")
        st.session_state.df = None
else:
    if st.session_state.df is None:
        st.session_state.df = generate_sample_data()
        st.sidebar.info("ℹ️ Using sample data. Upload a file to use your own data.")

if st.session_state.df is not None and not st.session_state.df.empty:
    df_normalized = normalize_columns(st.session_state.df)
    amazon_mode = is_amazon_mode(df_normalized)

    is_valid, missing_cols, detected_cols = validate_required_columns(df_normalized, amazon_mode)
    if not is_valid:
        st.error("### ❌ Missing Required Columns")
        st.write("**Required columns:**", ", ".join(missing_cols))
        st.write("**Detected columns:**", ", ".join(detected_cols) if detected_cols else "None")
        st.write("\n**Common column name synonyms supported:**")
        for canonical, synonyms in CANONICAL_COLUMNS.items():
            st.write(f"- **{canonical}**: {', '.join(synonyms[:3])}...")
        st.stop()

    if amazon_mode:
        df_processed = build_amazon_computed_fields(df_normalized)

        st.subheader("Product Name Mapping (Amazon)")
        mapping_upload = st.file_uploader(
            "Upload mapping CSV (columns: sku, product_name)",
            type=["csv"],
            key="sku_mapping_upload",
        )
        if mapping_upload is not None:
            try:
                mapping_df = pd.read_csv(mapping_upload)
                cols_lower = {c.lower().strip(): c for c in mapping_df.columns}
                sku_col = cols_lower.get("sku")
                name_col = cols_lower.get("product_name") or cols_lower.get("product name")
                if sku_col is None or name_col is None:
                    st.error("Mapping CSV must include columns: sku, product_name.")
                else:
                    for _, row in mapping_df[[sku_col, name_col]].iterrows():
                        sku = str(row[sku_col]).strip()
                        name = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
                        if sku:
                            st.session_state.product_name_map[sku] = name
            except Exception as exc:
                st.error(f"Failed to load mapping CSV: {exc}")

        if "sku" in df_processed.columns:
            sku_series = df_processed["sku"].astype(str).str.strip()
        elif "product_label" in df_processed.columns:
            sku_series = df_processed["product_label"].astype(str).str.strip()
        else:
            sku_series = pd.Series([""] * len(df_processed), index=df_processed.index)

        sku_series = sku_series[
            (sku_series.notna()) & (sku_series != "") & (sku_series.str.lower() != "nan")
        ]
        sku_list = sorted(sku_series.unique().tolist())

        default_name_by_sku: Dict[str, str] = {}
        if "sku" in df_processed.columns and "description" in df_processed.columns:
            desc_df = df_processed[["sku", "description"]].dropna()
            for sku, sub in desc_df.groupby("sku"):
                desc_series = sub["description"].astype(str).str.strip()
                desc_series = desc_series[
                    (desc_series != "") & (desc_series.str.lower() != "nan")
                ]
                if not desc_series.empty:
                    default_name_by_sku[str(sku)] = desc_series.iloc[0]

        for sku in sku_list:
            if sku not in st.session_state.product_name_map:
                st.session_state.product_name_map[sku] = default_name_by_sku.get(sku, "")

        editor_df = pd.DataFrame(
            {
                "sku": sku_list,
                "product_name": [st.session_state.product_name_map.get(sku, "") for sku in sku_list],
            }
        )
        edited_df = st.data_editor(
            editor_df,
            num_rows="fixed",
            use_container_width=True,
            column_config={
                "sku": st.column_config.TextColumn("SKU", disabled=True),
                "product_name": st.column_config.TextColumn("Product Name"),
            },
            key="sku_mapping_editor",
        )
        updated_map = dict(
            zip(
                edited_df["sku"].astype(str),
                edited_df["product_name"].fillna("").astype(str),
            )
        )
        st.session_state.product_name_map.update(
            {sku: name.strip() for sku, name in updated_map.items()}
        )

        download_df = pd.DataFrame(
            {
                "sku": sku_list,
                "product_name": [st.session_state.product_name_map.get(sku, "") for sku in sku_list],
            }
        )
        st.download_button(
            "Download mapping CSV",
            data=download_df.to_csv(index=False).encode("utf-8"),
            file_name="product_name_mapping.csv",
            mime="text/csv",
        )

        sku_series_full = (
            df_processed["sku"].astype(str).str.strip()
            if "sku" in df_processed.columns
            else df_processed.get("product_label", "").astype(str).str.strip()
        )
        name_series = sku_series_full.map(st.session_state.product_name_map).fillna("").astype(str).str.strip()
        display_series = sku_series_full.where(name_series == "", name_series + " (" + sku_series_full + ")")
        if "product_label" in df_processed.columns:
            display_series = display_series.where(display_series != "", df_processed["product_label"].astype(str))
        df_processed["product_display"] = display_series

        summary = compute_amazon_metrics(df_processed)
    else:
        if "date" in df_normalized.columns:
            df_normalized["date"] = pd.to_datetime(df_normalized["date"], errors="coerce")
        df_processed, summary = compute_metrics(df_normalized)

    st.session_state.df_processed = df_processed
    st.session_state.summary = summary

    st.sidebar.header("🔍 Filters")
    if "date" in df_processed.columns and df_processed["date"].notna().any():
        min_date = df_processed["date"].min().date()
        max_date = df_processed["date"].max().date()
        date_range = st.sidebar.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if len(date_range) == 2:
            start_date, end_date = date_range
            df_processed = df_processed[
                (df_processed["date"].dt.date >= start_date)
                & (df_processed["date"].dt.date <= end_date)
            ]
    else:
        st.sidebar.warning("⚠️ Date column not available")

    if amazon_mode:
        if "txn_type" in df_processed.columns:
            txn_options = ["All"] + sorted(df_processed["txn_type"].dropna().unique().tolist())
            selected_txn = st.sidebar.selectbox("Transaction Type", txn_options)
            if selected_txn != "All":
                df_processed = df_processed[df_processed["txn_type"] == selected_txn]

        if "location" in df_processed.columns and df_processed["location"].notna().any():
            state_options = ["All"] + sorted(df_processed["location"].dropna().unique().tolist())
            selected_state = st.sidebar.selectbox("State", state_options)
            if selected_state != "All":
                df_processed = df_processed[df_processed["location"] == selected_state]

        if "product_display" in df_processed.columns:
            product_options = ["All"] + sorted(df_processed["product_display"].dropna().unique().tolist())
            selected_display = st.sidebar.selectbox("Product", product_options)
            if selected_display != "All":
                if "sku" in df_processed.columns:
                    display_to_sku = (
                        df_processed[["sku", "product_display"]]
                        .dropna()
                        .drop_duplicates()
                        .set_index("product_display")["sku"]
                        .to_dict()
                    )
                    selected_sku = display_to_sku.get(selected_display, selected_display)
                    df_processed = df_processed[df_processed["sku"].astype(str).str.strip() == str(selected_sku)]
                else:
                    df_processed = df_processed[df_processed["product_display"] == selected_display]
        elif "product_label" in df_processed.columns:
            product_options = ["All"] + sorted(df_processed["product_label"].dropna().unique().tolist())
            selected_product = st.sidebar.selectbox("Product", product_options)
            if selected_product != "All":
                df_processed = df_processed[df_processed["product_label"] == selected_product]
    else:
        if "sku" in df_processed.columns:
            sku_options = ["All"] + sorted(df_processed["sku"].dropna().unique().tolist())
            selected_sku = st.sidebar.selectbox("Product SKU", sku_options)
            if selected_sku != "All":
                df_processed = df_processed[df_processed["sku"] == selected_sku]
        else:
            st.sidebar.warning("⚠️ SKU column not available")

        if "location" in df_processed.columns:
            location_options = ["All"] + sorted(df_processed["location"].dropna().unique().tolist())
            selected_location = st.sidebar.selectbox("Customer Location", location_options)
            if selected_location != "All":
                df_processed = df_processed[df_processed["location"] == selected_location]
        else:
            st.sidebar.warning("⚠️ Location column not available")

    if len(df_processed) == 0:
        st.warning("⚠️ No data matches the selected filters.")
        st.stop()

    summary = compute_amazon_metrics(df_processed) if amazon_mode else compute_metrics(df_processed)[1]

    if amazon_mode:
        st.sidebar.info("🛒 Amazon Settlement Mode")
        render_amazon_dashboard(df_processed, summary)
    else:
        render_generic_dashboard(df_processed, summary)

    st.header("🤖 AI Analysis Report")
    if st.button("Generate AI Analysis Report", type="primary"):
        analysis_text = simulate_ai_analysis(df_processed, summary, mode="amazon" if amazon_mode else "generic")
        st.markdown(analysis_text)

        with st.expander("💡 Future: OpenAI API Integration Code"):
            st.code(
                """
# Example code for OpenAI API integration (commented out for now)
# Uncomment and configure when ready to use OpenAI API

# import openai
# from dotenv import load_dotenv
# import os
#
# load_dotenv()
# openai.api_key = os.getenv("OPENAI_API_KEY")
#
# def generate_ai_analysis(df, summary):
#     prompt = f\"\"\"
#     Analyze this e-commerce data:
#     - Total Revenue: ${summary['total_revenue']:,.2f}
#     - Total Net Profit: ${summary['total_net_profit']:,.2f}
#     - Average Margin: {summary['avg_margin_pct']:.2f}%
#     - Number of transactions: {len(df)}
#
#     Provide insights and recommendations.
#     \"\"\"
#
#     response = openai.ChatCompletion.create(
#         model="gpt-4",
#         messages=[{"role": "user", "content": prompt}]
#     )
#
#     return response.choices[0].message.content
# """,
                language="python",
            )

    with st.expander("📋 View Raw Data"):
        st.dataframe(df_processed, use_container_width=True)
else:
    st.info("Please upload a data file or use the sample data that's been generated.")
