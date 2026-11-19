"""Cambridge scraper.

Website: https://thecambridgeshop.com
All products: https://thecambridgeshop.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Cambridge",
    "slug": "cambridge",
    "website": "https://thecambridgeshop.com",
    "strategy": "shopify_json",
    "origin": "https://thecambridgeshop.com",
    "all_products_url": "https://thecambridgeshop.com/collections/all",
    "api_url": "https://thecambridgeshop.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
