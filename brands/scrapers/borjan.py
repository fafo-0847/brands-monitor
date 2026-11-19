"""Borjan scraper.

Website: https://borjan.com.pk
All products: https://www.borjan.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Borjan",
    "slug": "borjan",
    "website": "https://borjan.com.pk",
    "strategy": "shopify_json",
    "origin": "https://www.borjan.com.pk",
    "all_products_url": "https://www.borjan.com.pk/collections/all",
    "api_url": "https://www.borjan.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
