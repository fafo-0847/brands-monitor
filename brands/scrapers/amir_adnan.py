"""Amir Adnan scraper.

Website: https://amiradnan.com
All products: https://amiradnan.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Amir Adnan",
    "slug": "amir-adnan",
    "website": "https://amiradnan.com",
    "strategy": "shopify_json",
    "origin": "https://amiradnan.com",
    "all_products_url": "https://amiradnan.com/collections/all",
    "api_url": "https://amiradnan.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
