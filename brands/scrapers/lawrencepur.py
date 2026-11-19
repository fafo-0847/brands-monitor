"""Lawrencepur scraper.

Website: https://lawrencepur.com
All products: https://lawrencepur.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Lawrencepur",
    "slug": "lawrencepur",
    "website": "https://lawrencepur.com",
    "strategy": "shopify_json",
    "origin": "https://lawrencepur.com",
    "all_products_url": "https://lawrencepur.com/collections/all",
    "api_url": "https://lawrencepur.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
