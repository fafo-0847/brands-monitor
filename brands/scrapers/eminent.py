"""Eminent scraper.

Website: https://eminent.pk
All products: https://eminent.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Eminent",
    "slug": "eminent",
    "website": "https://eminent.pk",
    "strategy": "shopify_json",
    "origin": "https://eminent.pk",
    "all_products_url": "https://eminent.pk/collections/all",
    "api_url": "https://eminent.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
