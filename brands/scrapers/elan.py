"""Elan scraper.

Website: https://www.elan.pk
All products: https://elan.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Elan",
    "slug": "elan",
    "website": "https://www.elan.pk",
    "strategy": "shopify_json",
    "origin": "https://elan.pk",
    "all_products_url": "https://elan.pk/collections/all",
    "api_url": "https://elan.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
