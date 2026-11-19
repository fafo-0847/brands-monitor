"""Aldo scraper.

Website: https://aldoshoes.pk
All products: https://aldoshoes.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Aldo",
    "slug": "aldo",
    "website": "https://aldoshoes.pk",
    "strategy": "shopify_json",
    "origin": "https://aldoshoes.pk",
    "all_products_url": "https://aldoshoes.pk/collections/all",
    "api_url": "https://aldoshoes.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
