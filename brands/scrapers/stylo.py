"""Stylo scraper.

Website: https://www.stylo.pk
All products: https://stylo.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Stylo",
    "slug": "stylo",
    "website": "https://www.stylo.pk",
    "strategy": "shopify_json",
    "origin": "https://stylo.pk",
    "all_products_url": "https://stylo.pk/collections/all",
    "api_url": "https://stylo.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
