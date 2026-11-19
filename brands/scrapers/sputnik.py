"""Sputnik scraper.

Website: https://sputnikfootwear.com
All products: https://sputnikfootwear.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Sputnik",
    "slug": "sputnik",
    "website": "https://sputnikfootwear.com",
    "strategy": "shopify_json",
    "origin": "https://sputnikfootwear.com",
    "all_products_url": "https://sputnikfootwear.com/collections/all",
    "api_url": "https://sputnikfootwear.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
