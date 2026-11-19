"""Retro Walk scraper.

Website: https://retrowalk.com
All products: https://www.retrowalk.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Retro Walk",
    "slug": "retro-walk",
    "website": "https://retrowalk.com",
    "strategy": "shopify_json",
    "origin": "https://www.retrowalk.com",
    "all_products_url": "https://www.retrowalk.com/collections/all",
    "api_url": "https://www.retrowalk.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
