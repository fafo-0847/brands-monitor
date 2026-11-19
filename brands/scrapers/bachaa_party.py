"""Bachaa Party scraper.

Website: https://bachaaparty.com
All products: https://bachaaparty.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Bachaa Party",
    "slug": "bachaa-party",
    "website": "https://bachaaparty.com",
    "strategy": "shopify_json",
    "origin": "https://bachaaparty.com",
    "all_products_url": "https://bachaaparty.com/collections/all",
    "api_url": "https://bachaaparty.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
