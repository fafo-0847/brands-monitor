"""Zara Shahjahan scraper.

Website: https://www.zarashahjahan.com
All products: https://zarashahjahan.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Zara Shahjahan",
    "slug": "zara-shahjahan",
    "website": "https://www.zarashahjahan.com",
    "strategy": "shopify_json",
    "origin": "https://zarashahjahan.com",
    "all_products_url": "https://zarashahjahan.com/collections/all",
    "api_url": "https://zarashahjahan.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
