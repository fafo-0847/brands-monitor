"""Focus Clothing scraper.

Website: https://focusclothing.pk
All products: https://focusclothing.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Focus Clothing",
    "slug": "focus-clothing",
    "website": "https://focusclothing.pk",
    "strategy": "shopify_json",
    "origin": "https://focusclothing.pk",
    "all_products_url": "https://focusclothing.pk/collections/all",
    "api_url": "https://focusclothing.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
