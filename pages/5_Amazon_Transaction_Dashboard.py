"""
Amazon seller transaction dashboard (HTML + Chart.js), matching the Claude web version.

Loads tab-separated settlement-style rows, with Overview / Products / Financials / Geography / Raw tabs.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent.parent


def _build_dashboard_html() -> str:
    body = (ROOT / "static/amazon_tx_part0.html").read_text(encoding="utf-8") + (
        ROOT / "static/amazon_tx_part1.html"
    ).read_text(encoding="utf-8")
    chart = (
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>'
    )
    sample = (ROOT / "static/amazon_sample.tsv").read_text(encoding="utf-8")
    sample_block = '<script type="text/plain" id="amazon-sample-tsv">\n' + sample + "\n</script>"
    js = "\n".join(
        (ROOT / f"static/amazon_tx_main_{i}.js").read_text(encoding="utf-8") for i in range(1, 6)
    )
    main_script = "<script>\n" + js + "\n</script>"
    leaflet_css = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
    leaflet_js  = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
    return (
        "<!DOCTYPE html><html lang=\"en\"><head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        + leaflet_css
        + "</head><body>"
        + body
        + chart
        + leaflet_js
        + sample_block
        + main_script
        + "</body></html>"
    )


st.set_page_config(page_title="Amazon Transactions", layout="wide")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display: none;}
[data-testid="stToolbar"] {display: none;}
[data-testid="stDecoration"] {display: none;}
[data-testid="stStatusWidget"] {display: none;}
.block-container {padding-top: 1rem !important; padding-bottom: 0rem !important;}
.stApp [data-testid="stHeader"] {display: none;}
.stAppHeader {height: 0px !important; display: none !important;}
</style>
""", unsafe_allow_html=True)

components.html(_build_dashboard_html(), height=4800, scrolling=True)
