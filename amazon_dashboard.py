"""
Amazon Dashboard — starter module.

Add Selling Partner API, Advertising API, or report ingestion here, then wire this
module into Streamlit pages or CLI scripts as needed.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Project root (this file lives at repo root)
ROOT = Path(__file__).resolve().parent


def get_amazon_config() -> dict[str, str]:
    """Read Amazon-related settings from the environment (add keys as you integrate)."""
    return {
        "region": os.getenv("AMAZON_REGION", ""),
        "marketplace_id": os.getenv("AMAZON_MARKETPLACE_ID", ""),
    }


def main() -> None:
    cfg = get_amazon_config()
    print("Amazon dashboard starter — config keys present:", {k: bool(v) for k, v in cfg.items()})


if __name__ == "__main__":
    main()
