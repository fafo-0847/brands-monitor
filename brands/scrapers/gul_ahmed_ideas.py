"""Gul Ahmed / Ideas scraper.

Website: https://www.gulahmedshop.com
All products: https://www.gulahmedshop.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Gul Ahmed / Ideas",
    "slug": "gul-ahmed-ideas",
    "website": "https://www.gulahmedshop.com",
    "strategy": "shopify_json",
    "origin": "https://www.gulahmedshop.com",
    "all_products_url": "https://www.gulahmedshop.com/collections/all",
    "api_url": "https://www.gulahmedshop.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
