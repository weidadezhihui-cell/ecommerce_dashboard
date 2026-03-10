"""
Product KPI Page
Filters + KPI indicators (Amazon Settlement)
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utils import to_money


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

    return {
        "units_sold": units_sold,
        "units_returned": units_returned,
        "net_units": net_units,
        "net_sales": net_sales,
        "net_proceeds": net_proceeds,
    }


def init_slicer_state() -> None:
    if "selected_years" not in st.session_state or st.session_state.selected_years is None:
        st.session_state.selected_years = None
    if "selected_years_widget" not in st.session_state or st.session_state.selected_years_widget is None:
        st.session_state.selected_years_widget = None
    if "selected_txn_bucket" not in st.session_state:
        st.session_state.selected_txn_bucket = "Order"


st.set_page_config(page_title="Product KPI", layout="wide")
st.markdown("# Product KPI")
st.caption("Amazon Settlement · Product KPI summary")

# Sidebar sub-navigation for Product KPI
st.sidebar.selectbox(
    "Product KPI Sections",
    ["Revenues", "Fees", "Net Proceeds"],
    key="product_kpi_section",
)

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
df_base["year"] = df_base["date"].dt.year

init_slicer_state()

available_years: List[int] = sorted([int(y) for y in df_base["year"].dropna().unique().tolist() if pd.notna(y)])
if not available_years:
    st.error("No valid dates found. Ensure date_time is parseable.")
    st.stop()

if "years_initialized" not in st.session_state:
    st.session_state.years_initialized = False

if not st.session_state.years_initialized:
    st.session_state.selected_years = list(available_years) if available_years else []
    st.session_state.selected_years_widget = list(st.session_state.selected_years)
    st.session_state.years_initialized = True

if st.session_state.selected_years is None:
    st.session_state.selected_years = list(available_years) if available_years else []
else:
    st.session_state.selected_years = [
        int(y) for y in st.session_state.selected_years if int(y) in available_years
    ] or (list(available_years) if available_years else [])
if st.session_state.selected_years_widget is None:
    st.session_state.selected_years_widget = list(st.session_state.selected_years)

st.markdown(
    """
    <style>
    /* Keep Filters + KPI header visible while scrolling (main content only) */
    section[data-testid="stMain"] div:has(> #sticky-header-anchor) {
        position: sticky;
        top: 0;
        z-index: 1000;
        background: #ffffff;
        padding: 8px 0 6px 0;
        border-bottom: 1px solid #f0f2f6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container():
    st.markdown("<div id='sticky-header-anchor'></div>", unsafe_allow_html=True)
    st.markdown("**Filters**")
    row1 = st.columns([2.0, 1.0])

    with row1[0]:
        st.multiselect(
            "Year",
            options=available_years,
            default=st.session_state.selected_years_widget,
            key="selected_years_widget",
        )
        st.session_state.selected_years = [
            int(y) for y in st.session_state.selected_years_widget if int(y) in available_years
        ]

    with row1[1]:
        st.write("")
        if st.button("Reset"):
            st.session_state.selected_years = list(available_years) if available_years else []
            st.session_state.selected_years_widget = list(st.session_state.selected_years)
            st.rerun()

    st.caption("These selections control the summary numbers.")

    years_label_kpi = (
        ", ".join(str(int(y)) for y in st.session_state.selected_years if pd.notna(y))
        if st.session_state.selected_years
        else "(none)"
    )

    st.markdown("## Key Performance Indicators")
    st.markdown(
        f"<div style='width:100%;'>"
        f"<div style='text-align:center; font-size:1.4em; font-weight:700;'>All Products</div>"
        f"<div style='text-align:center; font-size:1.2em;'>Years: {years_label_kpi}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<hr style='border:0; border-top:1px solid #e6e6e6; margin:10px 0 8px 0;'>",
        unsafe_allow_html=True,
    )

mask = pd.Series(True, index=df_base.index)
if st.session_state.selected_years:
    selected_years_set = set(int(y) for y in st.session_state.selected_years)
    available_years_set = set(int(y) for y in available_years)
    include_nan_years = selected_years_set == available_years_set
    mask &= df_base["year"].isin(st.session_state.selected_years) | (
        include_nan_years & df_base["year"].isna()
    )
else:
    mask &= False

df_scope = df_base[mask].copy()
if df_scope.empty:
    st.warning("No data for selected Product/Year selection.")
    st.stop()

kpis = compute_kpis(df_scope)

# --- SECTION 1: REVENUES ---
st.markdown(
    "<div style='text-align:left; font-family:sans-serif; font-weight:700; font-size:1.1rem; margin-bottom:10px; color:#1f2937;'>Revenues</div>",
    unsafe_allow_html=True,
)

# Shared CSS for consistent font styling across Streamlit markdown and HTML component
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    .kpi-container {
        font-family: 'Inter', sans-serif;
    }
    .kpi-label { 
        font-family: 'Inter', sans-serif;
        font-size: 13px; 
        font-weight: 600; 
        color: #6B7280; /* Cool Gray 500 */
        text-align: center; 
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-value { 
        font-family: 'Inter', sans-serif;
        font-size: 28px; 
        font-weight: 700; 
        color: #111827; /* Gray 900 */
        margin-top: 6px; 
        text-align: center; 
    }
    /* UPDATED: Bigger and Blacker for Revenue Sub-values */
    .kpi-sub {
        font-family: 'Inter', sans-serif;
        font-size: 16px; /* Increased from 14px */
        font-weight: 600; /* Bolder */
        color: #111827; /* Black/Gray 900 */
        text-align: center;
        margin-top: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

sales_series = safe_num(df_scope["product_sales"]) if "product_sales" in df_scope.columns else pd.Series(0, index=df_scope.index)
txn_series = df_scope.get("txn_type", pd.Series([""] * len(df_scope), index=df_scope.index)).astype(str)
is_order = bucket_mask(txn_series, "Order")
is_refund = bucket_mask(txn_series, "Refund")
sales_order = float(sales_series[is_order].sum())
sales_refund = float(sales_series[is_refund].sum())
sales_refund_abs = abs(sales_refund)
net_sales_value = float(sales_order - sales_refund_abs)
# Sanity: fees + net proceeds = net sales value
total_amazon_fees = float(net_sales_value - kpis["net_proceeds"])
total_amazon_fees_display = -abs(total_amazon_fees)
return_rate = (kpis["units_returned"] / kpis["units_sold"]) if kpis["units_sold"] else 0

# ALIGNMENT: Match Flowchart Columns (28% - 28% - 44%)
r_col1, r_col2, r_col3 = st.columns([0.28, 0.28, 0.44])

with r_col1:
    st.markdown(
        f"<div class='kpi-label'>Units Sold</div>"
        f"<div class='kpi-value'>${sales_order:,.0f}</div>"
        f"<div class='kpi-sub'>({kpis['units_sold']:,.0f})</div>",
        unsafe_allow_html=True,
    )
with r_col2:
    st.markdown(
        f"<div class='kpi-label'>Units Returned | Rate</div>"
        f"<div class='kpi-value'>-${sales_refund_abs:,.0f}</div>"
        f"<div class='kpi-sub'>({kpis['units_returned']:,.0f} | {return_rate:.1%})</div>",
        unsafe_allow_html=True,
    )
with r_col3:
    st.markdown(
        f"<div class='kpi-label'>Net Units Sold</div>"
        f"<div class='kpi-value'>${net_sales_value:,.0f}</div>"
        f"<div class='kpi-sub'>({kpis['net_units']:,.0f})</div>",
        unsafe_allow_html=True,
    )

# ---------- Secondary settlement KPIs ----------
txn_series = df_scope.get("txn_type", pd.Series([""] * len(df_scope), index=df_scope.index)).astype(str)
if "type" in df_scope.columns:
    fallback_type = df_scope["type"].astype(str)
    txn_series = txn_series.where(txn_series.str.strip() != "", fallback_type)
txn_series = txn_series.astype(str).str.strip()
desc_series = df_scope.get("description", pd.Series([""] * len(df_scope), index=df_scope.index)).astype(str)
type_series = df_scope.get("type", pd.Series([""] * len(df_scope), index=df_scope.index)).astype(str)
txn_text = (txn_series + " " + type_series + " " + desc_series).astype(str).str.strip()
qty_series = safe_num(df_scope["quantity"]) if "quantity" in df_scope.columns else pd.Series(0, index=df_scope.index)
total_series = safe_num(df_scope["total"]) if "total" in df_scope.columns else pd.Series(0, index=df_scope.index)

txn_lower = txn_text.str.lower()
m_adjust = txn_lower.str.contains("adjustment", na=False)
m_liq = txn_lower.str.contains("liquidation", na=False)  # includes Liquidations Adjustments
m_service_fee = txn_lower.str.contains("service fee", na=False)
m_type_only = txn_series.astype(str).str.strip().str.lower()
m_fba_inv_fee = m_type_only.str.contains(r"fba inventory fee", case=False, na=False)
m_transfer = txn_lower.str.contains("transfer|disbursement|payout", na=False)
m_deals_fee = txn_series.apply(_is_placeholder)

adj_qty = float(qty_series[m_adjust].sum())
adj_total = float(total_series[m_adjust].sum())
liq_qty = float(qty_series[m_liq].sum())
liq_total = float(total_series[m_liq].sum())
service_fee_total = float(total_series[m_service_fee].sum())
fba_inv_fee_total = float(total_series[m_fba_inv_fee].sum())
transfer_total = float(total_series[m_transfer].sum())
deals_fee_total = float(total_series[m_deals_fee].sum())
amazon_fees_on_product = float(
    total_series[is_order | is_refund].sum() - sales_series[is_order | is_refund].sum()
)
amazon_fees_on_product_display = -abs(amazon_fees_on_product)
m_or = (bucket_mask(txn_series, "Order") | bucket_mask(txn_series, "Refund")) & ~m_transfer
col_lookup = {c.lower(): c for c in df_scope.columns}
promo_col = col_lookup.get("promotional_rebates") or next(
    (c for c in df_scope.columns if "promotional" in c.lower() and "rebate" in c.lower()),
    None,
)
ship_col = col_lookup.get("shipping_credits") or next(
    (c for c in df_scope.columns if "shipping" in c.lower() and "credit" in c.lower()),
    None,
)
ship_tax_col = col_lookup.get("shipping_credits_tax") or next(
    (c for c in df_scope.columns if "shipping" in c.lower() and "tax" in c.lower()),
    None,
)

selling_fees_total = float(
    safe_num(df_scope["selling_fees"])[m_or].sum() if "selling_fees" in df_scope.columns else 0
)
fba_fees_total = float(
    safe_num(df_scope["fba_fees"])[m_or].sum() if "fba_fees" in df_scope.columns else 0
)
promo_rebates_total = float(safe_num(df_scope[promo_col])[m_or].sum() if promo_col else 0)
shipping_credits_total = float(safe_num(df_scope[ship_col])[m_or].sum() if ship_col else 0)
shipping_credits_tax_total = float(safe_num(df_scope[ship_tax_col])[m_or].sum() if ship_tax_col else 0)
shipping_credits_net = float(shipping_credits_total + shipping_credits_tax_total)
other_amazon_fees_on_product = float(
    amazon_fees_on_product
    - selling_fees_total
    - fba_fees_total
    - promo_rebates_total
    - shipping_credits_net
)
other_fees_total = float(
    total_amazon_fees_display
    - amazon_fees_on_product_display
    - adj_total
    - liq_total
    - service_fee_total
    - fba_inv_fee_total
    - deals_fee_total
)
other_fees_display = other_fees_total

# --- SECTION 2: FEES ---
# 1. Grouping: Combine Adjustment + Liquidations
combined_adj_total = adj_total + liq_total

# 2. Renaming: Update Labels
ops_label_display = "Amazon Fees and Adjustment on Operations"

# 3. Define Lists for Dynamic Sorting
# Format: {'label': 'Display Name', 'value': float_value}
product_items = [
    {"label": "Selling Fees", "value": selling_fees_total},
    {"label": "FBA Fees", "value": fba_fees_total},
    {"label": "Promotional Rebates", "value": promo_rebates_total},
    {"label": "Shipping Credits", "value": shipping_credits_net},  # Renamed from (net)
    {"label": "Other Product Fees", "value": other_amazon_fees_on_product},
]

ops_items = [
    {"label": "Adjustment", "value": combined_adj_total},  # Combined value
    {"label": "Service Fee", "value": service_fee_total},
    {"label": "FBA Inventory Fee", "value": fba_inv_fee_total},
    {"label": "Deals Fee", "value": deals_fee_total},
    {"label": "Other Ops Fees", "value": other_fees_display},
]

# 4. Sorting: Smallest (Most Negative) -> Largest (Most Positive)
product_items.sort(key=lambda x: x["value"])
ops_items.sort(key=lambda x: x["value"])

# 5. Percentage Logic (Fixed to sum to 100%)
amazon_fees_on_operations_display = float(total_amazon_fees_display - amazon_fees_on_product_display)
total_fees_abs = abs(total_amazon_fees) if abs(total_amazon_fees) > 0 else 1.0

pct_prod = abs(amazon_fees_on_product) / total_fees_abs
pct_ops = 1.0 - pct_prod  # Force remainder to ensure 100% match

# Format Strings for Parent Nodes (Split into Value and Pct)
val_prod_str = f"${amazon_fees_on_product_display:,.0f}"
pct_prod_str = f"({pct_prod:.1%})"

val_ops_str = f"${amazon_fees_on_operations_display:,.0f}"
pct_ops_str = f"({pct_ops:.1%})"

# Helper to generate leaf HTML dynamically
def generate_leaf_html(items, start_index):
    html_parts = []
    total_denominator = abs(total_amazon_fees) if total_amazon_fees != 0 else 1.0

    for i, item in enumerate(items):
        val = item["value"]
        # Calculate % of Total Fees
        pct = abs(val) / total_denominator
        pct_fmt = f"{pct:.1%}"

        node_id = f"node-dynamic-{start_index + i}"
        html = f"""
        <div class="fees-node leaf-node" id="{node_id}">
            <span class="kpi-label-leaf">{item['label']}:</span>
            <span class="kpi-value-leaf">${val:,.0f} <span style="font-weight:400; color:#6B7280; font-size:0.85em; margin-left:4px;">({pct_fmt})</span></span>
        </div>
        """
        html_parts.append(html)
    return "\n".join(html_parts)

# Generate HTML
product_leaves_html = generate_leaf_html(product_items, 100)
ops_leaves_html = generate_leaf_html(ops_items, 200)

st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:left; font-family:sans-serif; font-weight:700; font-size:1.1rem; color:#1f2937;'>Fees</div>",
    unsafe_allow_html=True,
)

fees_flow_html = f"""
<div style="width:100%; margin-top:10px;" id="fees-flow-container">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      margin: 0;
      color: #111827;
    }}
    
    /* Container: Height increased to prevent scrollbar */
    .fees-flow {{
      display: grid;
      grid-template-columns: 28% 28% 44%;
      gap: 0;
      position: relative;
      padding: 30px 10px;
      border: 1px solid #E5E7EB;
      border-radius: 12px;
      background: #FAFAFA;
      min-height: 900px; /* Taller height for full view */
      height: auto;
      overflow: visible; /* Disable internal scrollbar */
    }}
    
    .fees-col {{
      display: flex;
      flex-direction: column;
      position: relative;
      z-index: 2;
      justify-content: center;
      overflow: visible;
    }}
    
    .fees-col.leaves {{
      display: grid;
      grid-template-rows: 1fr 1fr;
      padding-left: 20px;
      gap: 0; 
      justify-items: start;
    }}

    .fees-leaf-group {{
      display: flex; /* Flex by default (Expanded) */
      flex-direction: column;
      gap: 16px;
      transition: opacity 0.3s ease;
      width: 100%;
    }}

    #group-product {{ align-self: start; padding-top: 60px; }}
    #group-ops {{ align-self: start; padding-top: 60px; }}
    
    /* Standard Node */
    .fees-node {{
      background: #ffffff;
      border: 1px solid #E5E7EB;
      border-radius: 10px;
      padding: 16px 14px;
      text-align: center;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      min-width: 170px;
      max-width: 95%;
      margin: 0 auto;
      position: relative;
      z-index: 10;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }}

    .node-clickable {{
      cursor: pointer;
      border: 1px solid #D1D5DB;
      transition: all 0.2s ease;
    }}
    .node-clickable:hover {{
      box-shadow: 0 8px 12px -3px rgba(0, 0, 0, 0.1);
      border-color: #9CA3AF;
      transform: translateY(-1px);
    }}

    /* Click Hint Badge */
    .click-hint {{
        margin-top: 8px;
        padding: 4px 10px;
        background-color: #F3F4F6;
        color: #6B7280;
        font-size: 10px;
        font-weight: 600;
        border-radius: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .node-clickable:hover .click-hint {{
        background-color: #E5E7EB;
        color: #374151;
    }}

    .leaf-node {{
      background: #ffffff;
      padding: 12px 16px;
      border-radius: 8px;
      border: 1px solid #F3F4F6;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
      
      display: flex;
      flex-direction: row;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      width: fit-content;
      min-width: 250px;
      margin-left: 20px;
    }}

    /* Typography */
    .kpi-label {{ 
      font-size: 12px; font-weight: 600; color: #6B7280; 
      text-transform: uppercase; letter-spacing: 0.05em; line-height: 1.2; margin-bottom: 6px;
    }}
    .kpi-value {{ 
      font-size: 22px; font-weight: 700; color: #111827; line-height: 1.1;
    }}
    .kpi-pct {{
      font-size: 15px; font-weight: 600; color: #4B5563; margin-top: 2px;
    }}
    
    /* Leaf Typography - Increased Size */
    .kpi-label-leaf {{ font-size: 15px; font-weight: 500; color: #374151; }}
    .kpi-value-leaf {{ font-size: 15px; font-weight: 700; color: #111827; font-feature-settings: "tnum"; }}
    
    .fees-svg {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; pointer-events: none; overflow: visible; }}
  </style>

  <div class="fees-flow" id="fees-flow">
    <svg class="fees-svg" id="fees-flow-svg">
      <path id="p-total-product" stroke="#CBD5E1" stroke-width="2" fill="none"/>
      <path id="p-total-ops" stroke="#CBD5E1" stroke-width="2" fill="none"/>
      </svg>

    <div class="fees-col root">
        <div class="fees-node" id="node-total">
          <div class="kpi-label">Total Amazon Fees ($)</div>
          <div class="kpi-value">${total_amazon_fees_display:,.0f}</div>
        </div>
    </div>

    <div class="fees-col mid" style="justify-content: space-evenly; gap: 40px;">
        <div class="fees-node node-clickable" id="node-product" onclick="toggleGroup('group-product')">
          <div class="kpi-label">Amazon Fees on Product</div>
          <div class="kpi-value">{val_prod_str}</div>
          <div class="kpi-pct">{pct_prod_str}</div>
          <div class="click-hint">Toggle Details ▾</div>
        </div>
        <div class="fees-node node-clickable" id="node-ops" onclick="toggleGroup('group-ops')">
          <div class="kpi-label">{ops_label_display}</div>
          <div class="kpi-value">{val_ops_str}</div>
          <div class="kpi-pct">{pct_ops_str}</div>
          <div class="click-hint">Toggle Details ▾</div>
        </div>
    </div>

    <div class="fees-col leaves">
      <div class="fees-leaf-group" id="group-product">
        {product_leaves_html}
      </div>

      <div class="fees-leaf-group" id="group-ops">
        {ops_leaves_html}
      </div>
    </div>
  </div>
</div>
<script>
(function() {{
  const svg = document.getElementById("fees-flow-svg");
  const container = document.getElementById("fees-flow");
  
  // Toggle Visibility
  window.toggleGroup = function(id) {{
    var el = document.getElementById(id);
    if (el) {{
        el.style.display = (el.style.display === "none") ? "flex" : "none";
        layout(); // Redraw lines immediately
    }}
  }};
  
  function getPos(el) {{
    const rect = el.getBoundingClientRect();
    const contRect = container.getBoundingClientRect();
    return {{ x: rect.left - contRect.left, y: rect.top - contRect.top, midY: (rect.top - contRect.top) + (rect.height / 2), right: (rect.left - contRect.left) + rect.width, left: (rect.left - contRect.left) }};
  }}
  
  // Generate Dynamic Paths
  function createPaths(groupId, parentPos, prefix) {{
      const group = document.getElementById(groupId);
      if (!group || group.style.display === "none") return;
      
      const children = group.children;
      for (let i = 0; i < children.length; i++) {{
          const child = children[i];
          const pathId = "p-" + prefix + "-" + i;
          
          let path = document.getElementById(pathId);
          if (!path) {{
              path = document.createElementNS("http://www.w3.org/2000/svg", "path");
              path.setAttribute("id", pathId);
              path.setAttribute("stroke", "#E2E8F0");
              path.setAttribute("stroke-width", "2");
              path.setAttribute("fill", "none");
              svg.appendChild(path);
          }} else {{
              path.setAttribute("d", ""); // Clear if hidden
          }}
          
          const pLeaf = getPos(child);
          drawBezier(path, {{x: parentPos.right, y: parentPos.midY}}, {{x: pLeaf.left, y: pLeaf.midY}});
      }}
  }}
  
  // Hide paths if group is hidden
  function clearPaths(prefix, count) {{
      for (let i = 0; i < count; i++) {{
          const path = document.getElementById("p-" + prefix + "-" + i);
          if (path) path.setAttribute("d", "");
      }}
  }}

  function drawBezier(path, start, end) {{
    const deltaX = (end.x - start.x) * 0.55;
    const d = "M " + start.x + "," + start.y + " C " + (start.x + deltaX) + "," + start.y + " " + (end.x - deltaX) + "," + end.y + " " + end.x + "," + end.y;
    path.setAttribute("d", d);
  }}
  
  function layout() {{
    const nodeTotal = document.getElementById("node-total");
    const nodeProduct = document.getElementById("node-product");
    const nodeOps = document.getElementById("node-ops");
    if (!nodeTotal || !nodeProduct || !nodeOps) return;
    
    const pTotal = getPos(nodeTotal);
    const pProd = getPos(nodeProduct);
    const pOps = getPos(nodeOps);
    
    // Draw Main Branches
    const pathTP = document.getElementById("p-total-product");
    const pathTO = document.getElementById("p-total-ops");
    if(pathTP) drawBezier(pathTP, {{x: pTotal.right, y: pTotal.midY}}, {{x: pProd.left, y: pProd.midY}});
    if(pathTO) drawBezier(pathTO, {{x: pTotal.right, y: pTotal.midY}}, {{x: pOps.left, y: pOps.midY}});

    // Draw Leaves
    const groupProd = document.getElementById("group-product");
    if (groupProd && groupProd.style.display !== "none") {{
        createPaths("group-product", pProd, "prod");
    }} else {{
        // Basic cleanup for known max items if hidden
        clearPaths("prod", 10); 
    }}
    
    const groupOps = document.getElementById("group-ops");
    if (groupOps && groupOps.style.display !== "none") {{
        createPaths("group-ops", pOps, "ops");
    }} else {{
        clearPaths("ops", 10);
    }}
  }}
  
  window.addEventListener("resize", layout);
  setInterval(layout, 200);
  layout();
}})();
</script>
</div>
"""
# Increased height to 950 to ensure no internal scrollbar appears when fully expanded
components.html(fees_flow_html, height=950, scrolling=True)

# --- SECTION 3: NET PROCEEDS ---
st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
st.markdown("<div style='text-align:left; font-family:sans-serif; font-weight:700; font-size:1.1rem; color:#1f2937;'>Net Proceeds</div>", unsafe_allow_html=True)

# 28% for the First Column (Net Proceeds value) to align with "Total Amazon Fees" (Root Node) above
nc1, nc2 = st.columns([0.28, 0.72])
with nc1:
    st.markdown(
        f"<div class='kpi-label'>Net Proceeds ($)</div>"
        f"<div class='kpi-value'>${kpis['net_proceeds']:,.0f}</div>",
        unsafe_allow_html=True,
    )

# --- SECTION 4: FINANCIAL CHARTS ---
st.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)
st.markdown("<div style='text-align:left; font-family:sans-serif; font-weight:700; font-size:1.1rem; color:#1f2937;'>Financial Analysis</div>", unsafe_allow_html=True)

if "date" in df_scope.columns:
    import altair as alt

    # Create two columns for the charts
    chart_col1, chart_col2 = st.columns(2)

    # --- CHART 1: COST STRUCTURE (DONUT) ---
    with chart_col1:
        st.markdown("**Cost Structure Breakdown**")

        # Prepare Data for Pie Chart (Absolute values of major fee categories)
        # We use the calculated totals from the Fees section
        cost_data = pd.DataFrame([
            {"Category": "Selling Fees", "Value": abs(selling_fees_total)},
            {"Category": "FBA Fees", "Value": abs(fba_fees_total)},
            {"Category": "Promotions/Ads", "Value": abs(promo_rebates_total + deals_fee_total)},
            {"Category": "Service/Inventory", "Value": abs(service_fee_total + fba_inv_fee_total)},
            {"Category": "Adjustments/Other", "Value": abs(combined_adj_total + other_fees_display + other_amazon_fees_on_product)},
        ])

        # Filter out zero values to keep chart clean
        cost_data = cost_data[cost_data["Value"] > 0]

        base = alt.Chart(cost_data).encode(
            theta=alt.Theta("Value", stack=True)
        )

        pie = base.mark_arc(outerRadius=120, innerRadius=80).encode(
            color=alt.Color("Category", scale=alt.Scale(scheme="category10")),
            order=alt.Order("Value", sort="descending"),
            tooltip=["Category", alt.Tooltip("Value", format="$,.0f")],
        )

        text = base.mark_text(radius=140).encode(
            text=alt.Text("Value", format="$,.0s"),
            order=alt.Order("Value", sort="descending"),
            color=alt.value("black"),
        )

        st.altair_chart(pie + text, use_container_width=True)

    # --- CHART 2: NET SALES VS PROCEEDS (BAR) ---
    with chart_col2:
        st.markdown("**Net Sales vs. Net Proceeds (Monthly)**")

        # Prepare Data
        df_trend = df_scope.copy()
        df_trend["Month"] = df_trend["date"].dt.to_period("M").astype(str)

        bar_data = df_trend.groupby("Month").agg(
            Net_Sales=("product_sales", "sum"),     # Approximate Net Sales
            Net_Proceeds=("total", "sum"),
        ).reset_index()

        # Melt for Side-by-Side Bars
        bar_melt = bar_data.melt(
            id_vars=["Month"],
            value_vars=["Net_Sales", "Net_Proceeds"],
            var_name="Metric",
            value_name="Amount",
        )

        # Render Chart
        bars = alt.Chart(bar_melt).mark_bar().encode(
            x=alt.X("Month", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("Amount", title="Amount ($)"),
            color=alt.Color("Metric", scale=alt.Scale(range=["#3B82F6", "#10B981"])),
            xOffset="Metric",
            tooltip=["Month", "Metric", alt.Tooltip("Amount", format="$,.0f")],
        ).interactive()

        st.altair_chart(bars, use_container_width=True)

else:
    st.info("Charts require a 'date' column in the dataset.")

# --- SECTION 4: YEAR-OVER-YEAR TRENDS ---
st.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)
st.markdown("<div style='text-align:left; font-family:sans-serif; font-weight:700; font-size:1.1rem; color:#1f2937;'>Year-Over-Year Performance</div>", unsafe_allow_html=True)

if "date" in df_scope.columns:
    import altair as alt

    # 1. Data Prep for Seasonality
    df_trend = df_scope.copy()

    # Extract readable Month (Jan, Feb) and a Month Number (1, 2) for sorting
    df_trend["Month"] = df_trend["date"].dt.strftime("%b")
    df_trend["MonthNum"] = df_trend["date"].dt.month
    df_trend["Year"] = df_trend["date"].dt.year.astype(str)

    # Group by Year and Month
    # We use 'total' (Net Proceeds) as the key metric to track profitability
    seasonality_data = df_trend.groupby(["Year", "Month", "MonthNum"]).agg(
        Net_Proceeds=("total", "sum")
    ).reset_index()

    # 2. Build the Multi-Line Chart
    # X-Axis: Month (Sorted by MonthNum so Jan comes before Feb)
    # Y-Axis: Net Proceeds ($)
    # Color: Year (creates separate lines)

    chart = alt.Chart(seasonality_data).mark_line(point=True, strokeWidth=3).encode(
        x=alt.X("Month", sort=alt.EncodingSortField(field="MonthNum", order="ascending"), title="Month"),
        y=alt.Y("Net_Proceeds", title="Net Proceeds ($)"),
        color=alt.Color("Year", scale=alt.Scale(scheme="tableau10"), title="Year"),
        tooltip=[
            alt.Tooltip("Year", title="Year"),
            alt.Tooltip("Month", title="Month"),
            alt.Tooltip("Net_Proceeds", title="Net Proceeds", format="$,.0f"),
        ],
    ).properties(
        height=400
    ).interactive()

    st.altair_chart(chart, use_container_width=True)

    # Optional: Summary Table below chart
    with st.expander("View Monthly Data Table"):
        pivot_table = seasonality_data.pivot(index="Month", columns="Year", values="Net_Proceeds")
        # Sort index by month number
        pivot_table["sort_key"] = pivot_table.index.map(lambda x: pd.to_datetime(x, format="%b").month)
        pivot_table = pivot_table.sort_values("sort_key").drop(columns=["sort_key"])

        st.dataframe(pivot_table.style.format("${:,.0f}"), use_container_width=True)

else:
    st.info("Trend chart requires a 'date' column in the dataset.")


