"""Limelight scraper.

Website: https://www.limelight.pk
All products: https://www.limelight.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Limelight",
    "slug": "limelight",
    "website": "https://www.limelight.pk",
    "strategy": "shopify_json",
    "origin": "https://www.limelight.pk",
    "all_products_url": "https://www.limelight.pk/collections/all",
    "api_url": "https://www.limelight.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
