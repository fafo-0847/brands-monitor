"""Rastah scraper.

Website: https://rastah.co
All products: https://pk.rastah.co/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Rastah",
    "slug": "rastah",
    "website": "https://rastah.co",
    "strategy": "shopify_json",
    "origin": "https://pk.rastah.co",
    "all_products_url": "https://pk.rastah.co/collections/all",
    "api_url": "https://pk.rastah.co/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
