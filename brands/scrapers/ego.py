"""Ego scraper.

Website: https://wearego.com
All products: https://wearego.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Ego",
    "slug": "ego",
    "website": "https://wearego.com",
    "strategy": "shopify_json",
    "origin": "https://wearego.com",
    "all_products_url": "https://wearego.com/collections/all",
    "api_url": "https://wearego.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
