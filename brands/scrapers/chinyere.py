"""Chinyere scraper.

Website: https://www.chinyere.pk
All products: https://www.chinyere.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Chinyere",
    "slug": "chinyere",
    "website": "https://www.chinyere.pk",
    "strategy": "shopify_json",
    "origin": "https://www.chinyere.pk",
    "all_products_url": "https://www.chinyere.pk/collections/all",
    "api_url": "https://www.chinyere.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
