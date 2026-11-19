"""Hush Puppies scraper.

Website: https://www.hushpuppies.com.pk
All products: https://www.hushpuppies.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Hush Puppies",
    "slug": "hush-puppies",
    "website": "https://www.hushpuppies.com.pk",
    "strategy": "shopify_json",
    "origin": "https://www.hushpuppies.com.pk",
    "all_products_url": "https://www.hushpuppies.com.pk/collections/all",
    "api_url": "https://www.hushpuppies.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
