"""Ndure scraper.

Website: https://www.ndure.com
All products: https://www.ndure.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Ndure",
    "slug": "ndure",
    "website": "https://www.ndure.com",
    "strategy": "shopify_json",
    "origin": "https://www.ndure.com",
    "all_products_url": "https://www.ndure.com/collections/all",
    "api_url": "https://www.ndure.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
