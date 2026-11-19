"""Royal Tag scraper.

Website: https://royaltag.com.pk
All products: https://royaltag.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Royal Tag",
    "slug": "royal-tag",
    "website": "https://royaltag.com.pk",
    "strategy": "shopify_json",
    "origin": "https://royaltag.com.pk",
    "all_products_url": "https://royaltag.com.pk/collections/all",
    "api_url": "https://royaltag.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
