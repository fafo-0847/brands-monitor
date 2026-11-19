"""Batik scraper.

Website: https://batik.com.pk
All products: https://batik.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Batik",
    "slug": "batik",
    "website": "https://batik.com.pk",
    "strategy": "shopify_json",
    "origin": "https://batik.com.pk",
    "all_products_url": "https://batik.com.pk/collections/all",
    "api_url": "https://batik.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
