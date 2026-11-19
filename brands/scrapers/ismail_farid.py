"""Ismail Farid scraper.

Website: https://www.ismailfarid.com
All products: https://www.ismailfarid.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Ismail Farid",
    "slug": "ismail-farid",
    "website": "https://www.ismailfarid.com",
    "strategy": "shopify_json",
    "origin": "https://www.ismailfarid.com",
    "all_products_url": "https://www.ismailfarid.com/collections/all",
    "api_url": "https://www.ismailfarid.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
