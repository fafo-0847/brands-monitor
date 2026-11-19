"""Jafferjees scraper.

Website: https://jafferjees.com
All products: https://jafferjees.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Jafferjees",
    "slug": "jafferjees",
    "website": "https://jafferjees.com",
    "strategy": "shopify_json",
    "origin": "https://jafferjees.com",
    "all_products_url": "https://jafferjees.com/collections/all",
    "api_url": "https://jafferjees.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
