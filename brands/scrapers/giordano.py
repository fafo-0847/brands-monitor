"""Giordano scraper.

Website: https://giordanopk.com
All products: https://giordanopk.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Giordano",
    "slug": "giordano",
    "website": "https://giordanopk.com",
    "strategy": "shopify_json",
    "origin": "https://giordanopk.com",
    "all_products_url": "https://giordanopk.com/collections/all",
    "api_url": "https://giordanopk.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
