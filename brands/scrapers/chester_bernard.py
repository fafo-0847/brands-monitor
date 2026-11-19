"""Chester Bernard scraper.

Website: https://chesterbernard.com
All products: https://chesterbernard.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Chester Bernard",
    "slug": "chester-bernard",
    "website": "https://chesterbernard.com",
    "strategy": "shopify_json",
    "origin": "https://chesterbernard.com",
    "all_products_url": "https://chesterbernard.com/collections/all",
    "api_url": "https://chesterbernard.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
