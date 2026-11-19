"""MTJ scraper.

Website: https://mtjonline.com
All products: https://mtjonline.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "MTJ",
    "slug": "mtj",
    "website": "https://mtjonline.com",
    "strategy": "shopify_json",
    "origin": "https://mtjonline.com",
    "all_products_url": "https://mtjonline.com/collections/all",
    "api_url": "https://mtjonline.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
