"""Baroque scraper.

Website: https://baroque.pk
All products: https://baroque.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Baroque",
    "slug": "baroque",
    "website": "https://baroque.pk",
    "strategy": "shopify_json",
    "origin": "https://baroque.pk",
    "all_products_url": "https://baroque.pk/collections/all",
    "api_url": "https://baroque.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
