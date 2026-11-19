"""Ethnic scraper.

Website: https://pk.ethnc.com
All products: https://pk.ethnc.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Ethnic",
    "slug": "ethnic",
    "website": "https://pk.ethnc.com",
    "strategy": "shopify_json",
    "origin": "https://pk.ethnc.com",
    "all_products_url": "https://pk.ethnc.com/collections/all",
    "api_url": "https://pk.ethnc.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
