"""Bareeze scraper.

Website: https://www.bareeze.com
All products: https://bareeze.com/all-products
Strategy: bareeze_listing
Note: Next.js storefront: every top-level category (2 requests each via its load-more page), deduped by product ID.
"""
from brands.engine import run

CONFIG = {
    "name": "Bareeze",
    "slug": "bareeze",
    "website": "https://www.bareeze.com",
    "strategy": "bareeze_listing",
    "origin": "https://bareeze.com",
    "all_products_url": "https://bareeze.com/all-products",
    "category_sitemap": "https://www.bareeze.com/sitemap/sitemap_cat_0.xml",
    "skip_categories": [
        "test",
        "lookbook"
    ],
    "note": "Next.js storefront: every top-level category (2 requests each via its load-more page), deduped by product ID."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
