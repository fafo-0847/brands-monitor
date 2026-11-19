"""Asim Jofa scraper.

Website: https://asimjofa.com
All products: https://asimjofa.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Asim Jofa",
    "slug": "asim-jofa",
    "website": "https://asimjofa.com",
    "strategy": "shopify_json",
    "origin": "https://asimjofa.com",
    "all_products_url": "https://asimjofa.com/collections/all",
    "api_url": "https://asimjofa.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
