"""Lulusar scraper.

Website: https://lulusar.com
All products: https://www.lulusar.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Lulusar",
    "slug": "lulusar",
    "website": "https://lulusar.com",
    "strategy": "shopify_json",
    "origin": "https://www.lulusar.com",
    "all_products_url": "https://www.lulusar.com/collections/all",
    "api_url": "https://www.lulusar.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
