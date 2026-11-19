"""Khazanay scraper.

Website: https://khazanay.pk
All products: https://www.khazanay.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Khazanay",
    "slug": "khazanay",
    "website": "https://khazanay.pk",
    "strategy": "shopify_json",
    "origin": "https://www.khazanay.pk",
    "all_products_url": "https://www.khazanay.pk/collections/all",
    "api_url": "https://www.khazanay.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
