"""Uniworth scraper.

Website: https://uniworthshop.com
All products: https://uniworthshop.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Uniworth",
    "slug": "uniworth",
    "website": "https://uniworthshop.com",
    "strategy": "shopify_json",
    "origin": "https://uniworthshop.com",
    "all_products_url": "https://uniworthshop.com/collections/all",
    "api_url": "https://uniworthshop.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
