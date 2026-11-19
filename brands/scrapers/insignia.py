"""Insignia scraper.

Website: https://www.insignia.com.pk
All products: https://insignia.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Insignia",
    "slug": "insignia",
    "website": "https://www.insignia.com.pk",
    "strategy": "shopify_json",
    "origin": "https://insignia.com.pk",
    "all_products_url": "https://insignia.com.pk/collections/all",
    "api_url": "https://insignia.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
