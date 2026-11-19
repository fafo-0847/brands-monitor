"""Sana Safinaz scraper.

Website: https://www.sanasafinaz.com
All products: https://sanasafinaz.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Sana Safinaz",
    "slug": "sana-safinaz",
    "website": "https://www.sanasafinaz.com",
    "strategy": "shopify_json",
    "origin": "https://sanasafinaz.com",
    "all_products_url": "https://sanasafinaz.com/collections/all",
    "api_url": "https://sanasafinaz.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
