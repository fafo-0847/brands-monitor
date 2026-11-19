"""Engine scraper.

Website: https://engine.com.pk
All products: https://engine.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Engine",
    "slug": "engine",
    "website": "https://engine.com.pk",
    "strategy": "shopify_json",
    "origin": "https://engine.com.pk",
    "all_products_url": "https://engine.com.pk/collections/all",
    "api_url": "https://engine.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
