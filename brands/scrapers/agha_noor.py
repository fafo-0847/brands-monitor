"""Agha Noor scraper.

Website: https://aghanoorofficial.com
All products: https://pk.aghanoorofficial.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Agha Noor",
    "slug": "agha-noor",
    "website": "https://aghanoorofficial.com",
    "strategy": "shopify_json",
    "origin": "https://pk.aghanoorofficial.com",
    "all_products_url": "https://pk.aghanoorofficial.com/collections/all",
    "api_url": "https://pk.aghanoorofficial.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
