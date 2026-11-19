"""Shaffer scraper.

Website: https://shaffer.store
All products: https://shaffer.store/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Shaffer",
    "slug": "shaffer",
    "website": "https://shaffer.store",
    "strategy": "shopify_json",
    "origin": "https://shaffer.store",
    "all_products_url": "https://shaffer.store/collections/all",
    "api_url": "https://shaffer.store/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
