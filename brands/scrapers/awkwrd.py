"""AWKWRD scraper.

Website: https://www.awkwardxstore.com
All products: https://www.awkwardxstore.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "AWKWRD",
    "slug": "awkwrd",
    "website": "https://www.awkwardxstore.com",
    "strategy": "shopify_json",
    "origin": "https://www.awkwardxstore.com",
    "all_products_url": "https://www.awkwardxstore.com/collections/all",
    "api_url": "https://www.awkwardxstore.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
