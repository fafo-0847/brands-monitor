"""Mocciani scraper.

Website: https://mocciani.com.pk
All products: https://mocciani.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Mocciani",
    "slug": "mocciani",
    "website": "https://mocciani.com.pk",
    "strategy": "shopify_json",
    "origin": "https://mocciani.com.pk",
    "all_products_url": "https://mocciani.com.pk/collections/all",
    "api_url": "https://mocciani.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
