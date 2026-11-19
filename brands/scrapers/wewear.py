"""WeWear scraper.

Website: https://wewearpk.com
All products: https://wewearpk.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "WeWear",
    "slug": "wewear",
    "website": "https://wewearpk.com",
    "strategy": "shopify_json",
    "origin": "https://wewearpk.com",
    "all_products_url": "https://wewearpk.com/collections/all",
    "api_url": "https://wewearpk.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
