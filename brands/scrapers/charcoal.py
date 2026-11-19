"""Charcoal scraper.

Website: https://charcoal.com.pk
All products: https://charcoal.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Charcoal",
    "slug": "charcoal",
    "website": "https://charcoal.com.pk",
    "strategy": "shopify_json",
    "origin": "https://charcoal.com.pk",
    "all_products_url": "https://charcoal.com.pk/collections/all",
    "api_url": "https://charcoal.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
