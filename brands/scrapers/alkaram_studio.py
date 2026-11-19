"""Alkaram Studio scraper.

Website: https://www.alkaramstudio.com
All products: https://www.alkaramstudio.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Alkaram Studio",
    "slug": "alkaram-studio",
    "website": "https://www.alkaramstudio.com",
    "strategy": "shopify_json",
    "origin": "https://www.alkaramstudio.com",
    "all_products_url": "https://www.alkaramstudio.com/collections/all",
    "api_url": "https://www.alkaramstudio.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
