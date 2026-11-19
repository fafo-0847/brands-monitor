"""Groovy scraper.

Website: https://groovypakistan.com
All products: https://groovypakistan.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Groovy",
    "slug": "groovy",
    "website": "https://groovypakistan.com",
    "strategy": "shopify_json",
    "origin": "https://groovypakistan.com",
    "all_products_url": "https://groovypakistan.com/collections/all",
    "api_url": "https://groovypakistan.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
