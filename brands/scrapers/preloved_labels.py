"""Preloved Labels scraper.

Website: https://prelovedlabels.com
All products: https://prelovedlabels.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Preloved Labels",
    "slug": "preloved-labels",
    "website": "https://prelovedlabels.com",
    "strategy": "shopify_json",
    "origin": "https://prelovedlabels.com",
    "all_products_url": "https://prelovedlabels.com/collections/all",
    "api_url": "https://prelovedlabels.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
