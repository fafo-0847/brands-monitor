"""Diners scraper.

Website: https://diners.com.pk
All products: https://diners.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Diners",
    "slug": "diners",
    "website": "https://diners.com.pk",
    "strategy": "shopify_json",
    "origin": "https://diners.com.pk",
    "all_products_url": "https://diners.com.pk/collections/all",
    "api_url": "https://diners.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
