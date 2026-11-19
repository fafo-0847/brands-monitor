"""Edenrobe scraper.

Website: https://edenrobe.com
All products: https://edenrobe.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Edenrobe",
    "slug": "edenrobe",
    "website": "https://edenrobe.com",
    "strategy": "shopify_json",
    "origin": "https://edenrobe.com",
    "all_products_url": "https://edenrobe.com/collections/all",
    "api_url": "https://edenrobe.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
