"""Dynasty Fabrics scraper.

Website: https://www.dynastyfabrics.com
All products: https://www.dynastyfabrics.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Dynasty Fabrics",
    "slug": "dynasty-fabrics",
    "website": "https://www.dynastyfabrics.com",
    "strategy": "shopify_json",
    "origin": "https://www.dynastyfabrics.com",
    "all_products_url": "https://www.dynastyfabrics.com/collections/all",
    "api_url": "https://www.dynastyfabrics.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
