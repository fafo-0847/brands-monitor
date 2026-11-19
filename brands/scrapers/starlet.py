"""Starlet scraper.

Website: https://starlet.pk
All products: https://starlet.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Starlet",
    "slug": "starlet",
    "website": "https://starlet.pk",
    "strategy": "shopify_json",
    "origin": "https://starlet.pk",
    "all_products_url": "https://starlet.pk/collections/all",
    "api_url": "https://starlet.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
