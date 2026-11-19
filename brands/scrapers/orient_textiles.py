"""Orient Textiles scraper.

Website: https://www.shopatorient.com
All products: https://shopatorient.com/collections/all
Strategy: hydrogen_listing
Note: Shopify Hydrogen (headless): /collections/all listing pages; product pages only to confirm unclear stock and for sitemap products missing from the listing.
"""
from brands.engine import run

CONFIG = {
    "name": "Orient Textiles",
    "slug": "orient-textiles",
    "website": "https://www.shopatorient.com",
    "strategy": "hydrogen_listing",
    "origin": "https://shopatorient.com",
    "all_products_url": "https://shopatorient.com/collections/all",
    "collection_path": "/collections/all",
    "sitemaps": [
        "https://shopatorient.com/sitemap.xml"
    ],
    "note": "Shopify Hydrogen (headless): /collections/all listing pages; product pages only to confirm unclear stock and for sitemap products missing from the listing."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
