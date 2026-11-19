"""Nishat Linen scraper.

Website: https://nishatlinen.com
All products: https://nishatlinen.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Nishat Linen",
    "slug": "nishat-linen",
    "website": "https://nishatlinen.com",
    "strategy": "shopify_json",
    "origin": "https://nishatlinen.com",
    "all_products_url": "https://nishatlinen.com/collections/all",
    "api_url": "https://nishatlinen.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
