"""Saya scraper.

Website: https://saya.pk
All products: https://saya.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Saya",
    "slug": "saya",
    "website": "https://saya.pk",
    "strategy": "shopify_json",
    "origin": "https://saya.pk",
    "all_products_url": "https://saya.pk/collections/all",
    "api_url": "https://saya.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
