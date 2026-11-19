"""Bonanza Satrangi scraper.

Website: https://bonanzasatrangi.com
All products: https://bonanzasatrangi.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Bonanza Satrangi",
    "slug": "bonanza-satrangi",
    "website": "https://bonanzasatrangi.com",
    "strategy": "shopify_json",
    "origin": "https://bonanzasatrangi.com",
    "all_products_url": "https://bonanzasatrangi.com/collections/all",
    "api_url": "https://bonanzasatrangi.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
