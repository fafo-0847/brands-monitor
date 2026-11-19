"""Jadeno scraper.

Website: https://jadeno.pk
All products: https://jadeno.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Jadeno",
    "slug": "jadeno",
    "website": "https://jadeno.pk",
    "strategy": "shopify_json",
    "origin": "https://jadeno.pk",
    "all_products_url": "https://jadeno.pk/collections/all",
    "api_url": "https://jadeno.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
