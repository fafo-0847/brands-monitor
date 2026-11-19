"""Furor scraper.

Website: https://furorjeans.com
All products: https://furorjeans.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Furor",
    "slug": "furor",
    "website": "https://furorjeans.com",
    "strategy": "shopify_json",
    "origin": "https://furorjeans.com",
    "all_products_url": "https://furorjeans.com/collections/all",
    "api_url": "https://furorjeans.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
