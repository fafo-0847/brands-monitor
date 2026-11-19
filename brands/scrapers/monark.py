"""Monark scraper.

Website: https://monark.com.pk
All products: https://monark.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Monark",
    "slug": "monark",
    "website": "https://monark.com.pk",
    "strategy": "shopify_json",
    "origin": "https://monark.com.pk",
    "all_products_url": "https://monark.com.pk/collections/all",
    "api_url": "https://monark.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
