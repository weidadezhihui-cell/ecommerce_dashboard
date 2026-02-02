"""
Utility functions for e-commerce analytics dashboard.
Handles data loading, column normalization, and metrics computation.
"""

import csv
import io
import re
from typing import Tuple, Dict, Optional, List

import pandas as pd


# Canonical column names that the dashboard expects
CANONICAL_COLUMNS = {
    'date': ['date', 'date/time', 'date_time', 'order_date', 'transaction_date', 'created_at', 'timestamp'],
    'order_id': ['order_id', 'order id', 'order-id', 'order_number', 'transaction_id', 'id'],
    'sku': ['sku', 'product_sku', 'product_id', 'item_sku'],
    'location': ['location', 'state', 'customer_location', 'region', 'shipping_state'],
    'revenue': ['revenue', 'sales', 'total', 'total_revenue', 'amount', 'order_value'],
    'cogs': ['cogs', 'cost_of_goods_sold', 'cost', 'product_cost', 'unit_cost'],
    'ad_cost': ['ad_cost', 'advertising_cost', 'ad_spend', 'marketing_cost', 'ads'],
    'fees': ['fees', 'transaction_fees', 'platform_fees', 'processing_fees', 'fee'],
    # Amazon settlement specific: keep originals, add canonical copies
    'date_time': ['date/time', 'date time'],
    'txn_type': ['type', 'transaction type'],
    'product_sales': ['product sales', 'product sa'],
    'selling_fees': ['selling fees', 'selling fee'],
    'fba_fees': ['fba fees'],
    'other_transaction_fees': ['other transaction fees', 'other tran'],
    'order_state': ['order state', 'order stat'],
    'order_city': ['order city', 'order cit'],
    'total': ['total'],
    'description': ['description', 'descriptio'],
    'regulatory_fee': ['regulatory fee'],
    'tax_on_regulatory_fee': ['tax on regulatory fee'],
}

# Required columns for Amazon header detection (case-insensitive, ignore extra spaces)
# Must have at least: date/time (or date time), type, order id, total
_AMAZON_HEADER_REQUIRED = [
    ['date/time', 'date time'],   # date column: either form
    ['type'],
    ['order id', 'order-id'],
    ['total'],
]
_MAX_HEADER_SCAN_LINES = 80

# Required Amazon canonical columns for validate_amazon_columns
REQUIRED_AMAZON_CANONICAL = [
    'date_time', 'txn_type', 'total', 'sku', 'description',
    'product_sales', 'selling_fees', 'fba_fees', 'other_transaction_fees',
    'order_state', 'order_city',
]


# Timezone abbreviations to strip from date/time strings (order matters for regex)
_TZ_TOKENS = [
    'PST', 'PDT', 'EST', 'EDT', 'CST', 'CDT', 'MST', 'MDT',
    'UTC', 'AKST', 'AKDT', 'HST', 'ChST', 'GMT', 'AEST', 'AEDT',
]


def clean_amazon_datetime(s: str) -> str:
    """
    Remove trailing timezone abbreviations (PST, PDT, EST, etc.) from date/time strings.
    Does NOT parse to datetime; only strips timezone text so app.py / pandas can parse later.

    Args:
        s: Raw date/time string, e.g. "2024-01-15 10:30:00 PST" or "Jan 1, 2021 1.52E+10 PST"

    Returns:
        Cleaned string with timezone stripped, e.g. "2024-01-15 10:30:00"
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return s
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    # Build regex: optional space + one of the tokens + optional parenthetical suffix
    tz_pattern = re.compile(
        r'\s+(' + '|'.join(re.escape(t) for t in _TZ_TOKENS) + r')\s*(\([^)]*\))?\s*$',
        re.IGNORECASE
    )
    return tz_pattern.sub('', s).strip()


def _normalize_header_cell(cell: str) -> str:
    """Lowercase, strip, collapse extra spaces. Used for case-insensitive header matching."""
    return ' '.join(str(cell).strip().lower().split())


def _row_has_amazon_header(cells: List[str]) -> bool:
    """
    Return True iff this row has at least date/time (or date time), type, order id, total.
    Case-insensitive; extra spaces ignored. Each required group must match at least one cell.
    """
    norm = [_normalize_header_cell(c) for c in cells]
    for group in _AMAZON_HEADER_REQUIRED:
        found = False
        for n in norm:
            for g in group:
                if g == n or (len(g) > 2 and g in n):
                    found = True
                    break
            if found:
                break
        if not found:
            return False
    return True


def _detect_amazon_header_row(content: str) -> Optional[int]:
    """
    Scan only the first 80 lines of CSV for Amazon-style header
    (date/time or date time, type, order id, total).
    Return 0-based row index or None if not found.
    """
    reader = csv.reader(io.StringIO(content))
    for i, row in enumerate(reader):
        if i >= _MAX_HEADER_SCAN_LINES:
            break
        if not row:
            continue
        if _row_has_amazon_header(row):
            return i
    return None


def _find_date_time_column(df: pd.DataFrame) -> Optional[str]:
    """Return original column name that matches date/time (or date time), or None."""
    for col in df.columns:
        n = _normalize_header_cell(str(col))
        if n in ('date/time', 'date time') or ('date' in n and 'time' in n):
            return col
    return None


def validate_amazon_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Check which required Amazon canonical columns are present or missing.
    No external test frameworks; internal helper only.

    Args:
        df: DataFrame (typically after normalize_columns)

    Returns:
        {"present": [...], "missing": [...]} for REQUIRED_AMAZON_CANONICAL columns
    """
    cols = set(df.columns)
    present = [c for c in REQUIRED_AMAZON_CANONICAL if c in cols]
    missing = [c for c in REQUIRED_AMAZON_CANONICAL if c not in cols]
    return {"present": present, "missing": missing}


def load_data(uploaded_file: Optional[object]) -> Optional[pd.DataFrame]:
    """
    Load data from uploaded file (CSV or XLSX) or return None.

    CSV: Scans first 80 lines for Amazon-style header (date/time or date time,
    type, order id, total). If found, uses that row as header; else header=0.
    Strips timezone text (PST, PDT, etc.) from date/time column via
    clean_amazon_datetime. Does NOT parse to datetime; app.py handles that.

    Args:
        uploaded_file: Streamlit uploaded file object or None

    Returns:
        DataFrame with loaded data, or None if no file provided
    """
    if uploaded_file is None:
        return None

    try:
        file_extension = uploaded_file.name.split('.')[-1].lower()

        if file_extension == 'csv':
            raw = uploaded_file.read()
            content = raw.decode('utf-8-sig') if isinstance(raw, bytes) else str(raw)
            buf = io.StringIO(content)

            header_row = _detect_amazon_header_row(content)
            if header_row is not None:
                # Skip definition rows; use detected row as header (first line after skip)
                df = pd.read_csv(buf, header=header_row)

            else:
                buf.seek(0)
                df = pd.read_csv(buf)

            # Strip timezone only; do not parse to datetime
            dt_col = _find_date_time_column(df)
            if dt_col is not None:
                df[dt_col] = df[dt_col].apply(
                    lambda x: clean_amazon_datetime(x) if pd.notna(x) else x
                )
            return df

        if file_extension in ['xlsx', 'xls']:
            return pd.read_excel(uploaded_file, engine='openpyxl')

        raise ValueError(f"Unsupported file type: {file_extension}. Please upload CSV or XLSX.")

    except Exception as e:
        raise ValueError(f"Error loading file: {str(e)}")


# Amazon settlement canonicals: keep originals, add canonical copies (do not rename)
_AMAZON_CANONICAL_KEYS = {
    'date_time', 'txn_type', 'product_sales', 'selling_fees', 'fba_fees',
    'other_transaction_fees', 'order_state', 'order_city', 'total', 'description',
    'regulatory_fee', 'tax_on_regulatory_fee',
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names to canonical names by matching common synonyms.
    For Amazon settlement columns: KEEP originals and ADD canonical copies.

    Args:
        df: DataFrame with potentially non-standard column names

    Returns:
        DataFrame with originals preserved and canonical columns added where matched.
    """
    df_normalized = df.copy()
    column_mapping = {}
    amazon_canonical_additions = {}
    matched_columns = set()

    # Normalized (lower, strip, collapse spaces) -> original column name; keep first if duplicate
    norm_to_orig = {}
    for c in df.columns:
        n = _normalize_header_cell(c)
        if n not in norm_to_orig:
            norm_to_orig[n] = c

    # First pass: Amazon canonical columns (add copies, keep originals)
    for canonical_name, synonyms in CANONICAL_COLUMNS.items():
        if canonical_name not in _AMAZON_CANONICAL_KEYS:
            continue
        for syn in synonyms:
            n = _normalize_header_cell(syn)
            if n not in norm_to_orig:
                continue
            orig = norm_to_orig[n]
            if orig in matched_columns:
                break
            if canonical_name not in df_normalized.columns:
                amazon_canonical_additions[canonical_name] = orig
            matched_columns.add(orig)
            break

    # Second pass: Standard columns (rename to canonical)
    for canonical_name, synonyms in CANONICAL_COLUMNS.items():
        if canonical_name in _AMAZON_CANONICAL_KEYS:
            continue
        for syn in synonyms:
            n = _normalize_header_cell(syn)
            if n not in norm_to_orig:
                continue
            orig = norm_to_orig[n]
            if orig in matched_columns:
                break
            column_mapping[orig] = canonical_name
            matched_columns.add(orig)
            break

    df_normalized = df_normalized.rename(columns=column_mapping)

    for canonical_name, source_col in amazon_canonical_additions.items():
        if canonical_name not in df_normalized.columns:
            df_normalized[canonical_name] = df_normalized[source_col].copy()

    return df_normalized


def compute_metrics(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Compute net profit, margin percentage, and summary metrics.
    
    Args:
        df: DataFrame with normalized columns (date, revenue, cogs, ad_cost, fees)
        
    Returns:
        Tuple of (DataFrame with computed columns, summary dictionary)
    """
    df_metrics = df.copy()
    
    # Ensure numeric columns exist and are numeric, fill missing with 0
    numeric_cols = ['revenue', 'cogs', 'ad_cost', 'fees']
    for col in numeric_cols:
        if col in df_metrics.columns:
            df_metrics[col] = pd.to_numeric(df_metrics[col], errors='coerce').fillna(0)
        else:
            df_metrics[col] = 0
    
    # Compute net profit: revenue - cogs - ad_cost - fees
    df_metrics['net_profit'] = (
        df_metrics['revenue'] - 
        df_metrics['cogs'] - 
        df_metrics['ad_cost'] - 
        df_metrics['fees']
    )
    
    # Compute margin percentage: net_profit / revenue (handle divide-by-zero)
    df_metrics['margin_pct'] = df_metrics.apply(
        lambda row: (row['net_profit'] / row['revenue'] * 100) if row['revenue'] > 0 else 0,
        axis=1
    )
    
    # Compute summary metrics
    total_revenue = df_metrics['revenue'].sum()
    total_net_profit = df_metrics['net_profit'].sum()
    total_ad_spend = df_metrics['ad_cost'].sum()
    
    # Average margin percentage (weighted by revenue)
    if total_revenue > 0:
        avg_margin_pct = (total_net_profit / total_revenue) * 100
    else:
        avg_margin_pct = 0
    
    summary = {
        'total_revenue': total_revenue,
        'total_net_profit': total_net_profit,
        'total_ad_spend': total_ad_spend,
        'avg_margin_pct': avg_margin_pct
    }
    
    return df_metrics, summary


def generate_sample_data() -> pd.DataFrame:
    """
    Generate a sample dataset for demonstration when no file is uploaded.
    
    Returns:
        DataFrame with sample e-commerce data
    """
    import numpy as np
    from datetime import datetime, timedelta
    
    # Set random seed for reproducibility
    np.random.seed(42)
    
    # Generate 100 sample records
    n_records = 100
    start_date = datetime(2024, 1, 1)
    
    # Sample data
    skus = ['SKU-001', 'SKU-002', 'SKU-003', 'SKU-004', 'SKU-005']
    locations = ['Alberta', 'Ontario', 'British Columbia', 'Quebec', 'Manitoba']
    
    data = {
        'date': [start_date + timedelta(days=np.random.randint(0, 365)) for _ in range(n_records)],
        'order_id': [f'ORD-{i+1:04d}' for i in range(n_records)],
        'sku': np.random.choice(skus, n_records),
        'location': np.random.choice(locations, n_records),
        'revenue': np.random.uniform(50, 500, n_records).round(2),
    }
    
    df = pd.DataFrame(data)
    
    # Compute derived fields
    df['cogs'] = (df['revenue'] * np.random.uniform(0.3, 0.6, n_records)).round(2)
    df['ad_cost'] = (df['revenue'] * np.random.uniform(0.05, 0.15, n_records)).round(2)
    df['fees'] = (df['revenue'] * np.random.uniform(0.02, 0.05, n_records)).round(2)
    
    return df
