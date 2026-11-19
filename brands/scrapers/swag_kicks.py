"""Swag Kicks scraper.

Website: https://swag-kicks.com
All products: https://www.swag-kicks.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Swag Kicks",
    "slug": "swag-kicks",
    "website": "https://swag-kicks.com",
    "strategy": "shopify_json",
    "origin": "https://www.swag-kicks.com",
    "all_products_url": "https://www.swag-kicks.com/collections/all",
    "api_url": "https://www.swag-kicks.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
