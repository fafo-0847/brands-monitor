"""Zeesy scraper.

Website: https://zeesy.pk
All products: https://zeesy.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Zeesy",
    "slug": "zeesy",
    "website": "https://zeesy.pk",
    "strategy": "shopify_json",
    "origin": "https://zeesy.pk",
    "all_products_url": "https://zeesy.pk/collections/all",
    "api_url": "https://zeesy.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
