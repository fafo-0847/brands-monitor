"""Kross Kulture scraper.

Website: https://krosskulture.com
All products: https://krosskulture.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Kross Kulture",
    "slug": "kross-kulture",
    "website": "https://krosskulture.com",
    "strategy": "shopify_json",
    "origin": "https://krosskulture.com",
    "all_products_url": "https://krosskulture.com/collections/all",
    "api_url": "https://krosskulture.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
