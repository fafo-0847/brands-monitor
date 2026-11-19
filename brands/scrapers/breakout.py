"""Breakout scraper.

Website: https://www.breakout.com.pk
All products: https://www.breakout.com.pk/collections/all
Strategy: hydrogen_listing
Note: Shopify Hydrogen (headless): /collections/all listing pages; product pages only to confirm unclear stock and for sitemap products missing from the listing.
"""
from brands.engine import run

CONFIG = {
    "name": "Breakout",
    "slug": "breakout",
    "website": "https://www.breakout.com.pk",
    "strategy": "hydrogen_listing",
    "origin": "https://www.breakout.com.pk",
    "all_products_url": "https://www.breakout.com.pk/collections/all",
    "collection_path": "/collections/all",
    "sitemaps": [
        "https://www.breakout.com.pk/sitemap.xml"
    ],
    "note": "Shopify Hydrogen (headless): /collections/all listing pages; product pages only to confirm unclear stock and for sitemap products missing from the listing."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
