"""Zellbury scraper.

Website: https://zellbury.com
All products: https://zellbury.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Zellbury",
    "slug": "zellbury",
    "website": "https://zellbury.com",
    "strategy": "shopify_json",
    "origin": "https://zellbury.com",
    "all_products_url": "https://zellbury.com/collections/all",
    "api_url": "https://zellbury.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
