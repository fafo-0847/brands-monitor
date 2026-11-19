"""Manto scraper.

Website: https://www.shopmanto.com
All products: https://www.shopmanto.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Manto",
    "slug": "manto",
    "website": "https://www.shopmanto.com",
    "strategy": "shopify_json",
    "origin": "https://www.shopmanto.com",
    "all_products_url": "https://www.shopmanto.com/collections/all",
    "api_url": "https://www.shopmanto.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
