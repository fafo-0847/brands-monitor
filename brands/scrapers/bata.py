"""Bata scraper.

Website: https://www.bata.com.pk
All products: https://www.bata.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Bata",
    "slug": "bata",
    "website": "https://www.bata.com.pk",
    "strategy": "shopify_json",
    "origin": "https://www.bata.com.pk",
    "all_products_url": "https://www.bata.com.pk/collections/all",
    "api_url": "https://www.bata.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
