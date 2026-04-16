"""
Fetch abandoned checkouts from Shopify Admin REST API and append to a CSV archive.

Requires: pip install ShopifyAPI pandas python-dotenv
Scopes: read_orders (and access to protected customer data where applicable).

REST checkouts are exposed as shopify.Checkout — there is no AbandonedCheckout class
in the Python library.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import shopify


def _customer_display_name(checkout) -> str:
    customer = getattr(checkout, "customer", None)
    if customer is None:
        return "N/A"
    first = getattr(customer, "first_name", None) or ""
    last = getattr(customer, "last_name", None) or ""
    name = f"{first} {last}".strip()
    return name if name else "N/A"


def _iter_all_checkouts(**params):
    """Iterate every checkout across REST cursor pages (default page size 250)."""
    params.setdefault("limit", 250)
    page = shopify.Checkout.find(**params)
    while True:
        for c in page:
            yield c
        if not page.has_next_page():
            break
        page = page.next_page()


def sync_abandoned_checkouts(session, days_back: int = 7, archive_path: str = "abandoned_archive.csv") -> str:
    shopify.ShopifyResource.activate_session(session)

    created_at_min = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

    data = []
    for c in _iter_all_checkouts(created_at_min=created_at_min):
        data.append(
            {
                "id": str(c.id),
                "created_at": c.created_at,
                "customer_name": _customer_display_name(c),
                "email": getattr(c, "email", None),
                "total_price": getattr(c, "total_price", None),
                "abandoned_checkout_url": getattr(c, "abandoned_checkout_url", None),
            }
        )

    new_df = pd.DataFrame(data)
    if new_df.empty:
        return "No checkouts in window; archive unchanged."

    try:
        existing_df = pd.read_csv(archive_path, dtype={"id": str})
        final_df = pd.concat([existing_df, new_df], ignore_index=True).drop_duplicates(subset=["id"], keep="last")
    except FileNotFoundError:
        final_df = new_df

    final_df.to_csv(archive_path, index=False)
    return f"Fetched {len(new_df)} checkouts in window; archive has {len(final_df)} rows."


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent / ".env")
    except ImportError:
        pass

    shop_url = os.environ.get("SHOPIFY_SHOP_URL", "").strip()
    token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "").strip()
    api_version = os.environ.get("SHOPIFY_API_VERSION", "2024-10").strip()

    if not shop_url or not token:
        raise SystemExit(
            "Set SHOPIFY_SHOP_URL (e.g. your-store.myshopify.com) and SHOPIFY_ACCESS_TOKEN in the environment."
        )

    session = shopify.Session(shop_url, api_version, token)
    print(sync_abandoned_checkouts(session))
