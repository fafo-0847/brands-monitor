"""Beechtree scraper.

Website: https://beechtree.pk
All products: https://beechtree.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Beechtree",
    "slug": "beechtree",
    "website": "https://beechtree.pk",
    "strategy": "shopify_json",
    "origin": "https://beechtree.pk",
    "all_products_url": "https://beechtree.pk/collections/all",
    "api_url": "https://beechtree.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
