"""Unze London scraper.

Website: https://www.unze.com.pk
All products: https://unze.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Unze London",
    "slug": "unze-london",
    "website": "https://www.unze.com.pk",
    "strategy": "shopify_json",
    "origin": "https://unze.com.pk",
    "all_products_url": "https://unze.com.pk/collections/all",
    "api_url": "https://unze.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
