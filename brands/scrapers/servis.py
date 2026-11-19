"""Servis scraper.

Website: https://www.servis.pk
All products: https://servis.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Servis",
    "slug": "servis",
    "website": "https://www.servis.pk",
    "strategy": "shopify_json",
    "origin": "https://servis.pk",
    "all_products_url": "https://servis.pk/collections/all",
    "api_url": "https://servis.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
