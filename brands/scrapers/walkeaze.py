"""Walkeaze scraper.

Website: https://walkeaze.com
All products: https://walkeaze.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Walkeaze",
    "slug": "walkeaze",
    "website": "https://walkeaze.com",
    "strategy": "shopify_json",
    "origin": "https://walkeaze.com",
    "all_products_url": "https://walkeaze.com/collections/all",
    "api_url": "https://walkeaze.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
