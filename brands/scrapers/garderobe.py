"""Garderobe scraper.

Website: https://garderobe.pk
All products: https://garderobe.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Garderobe",
    "slug": "garderobe",
    "website": "https://garderobe.pk",
    "strategy": "shopify_json",
    "origin": "https://garderobe.pk",
    "all_products_url": "https://garderobe.pk/collections/all",
    "api_url": "https://garderobe.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
