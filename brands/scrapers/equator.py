"""Equator scraper.

Website: https://equatorstores.com
All products: https://equatorstores.com/collections/all
Strategy: hydrogen_listing
Note: Shopify Hydrogen (headless): /collections/all listing pages; product pages only to confirm unclear stock and for sitemap products missing from the listing.
"""
from brands.engine import run

CONFIG = {
    "name": "Equator",
    "slug": "equator",
    "website": "https://equatorstores.com",
    "strategy": "hydrogen_listing",
    "origin": "https://equatorstores.com",
    "all_products_url": "https://equatorstores.com/collections/all",
    "collection_path": "/collections/all",
    "sitemaps": [
        "https://equatorstores.com/sitemap.xml"
    ],
    "note": "Shopify Hydrogen (headless): /collections/all listing pages; product pages only to confirm unclear stock and for sitemap products missing from the listing."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
