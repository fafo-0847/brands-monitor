"""Zeen scraper.

Website: https://zeenwoman.com
All products: https://zeenwoman.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Zeen",
    "slug": "zeen",
    "website": "https://zeenwoman.com",
    "strategy": "shopify_json",
    "origin": "https://zeenwoman.com",
    "all_products_url": "https://zeenwoman.com/collections/all",
    "api_url": "https://zeenwoman.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
