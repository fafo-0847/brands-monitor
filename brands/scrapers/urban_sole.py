"""Urban Sole scraper.

Website: https://urbansole.com.pk
All products: https://www.urbansole.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Urban Sole",
    "slug": "urban-sole",
    "website": "https://urbansole.com.pk",
    "strategy": "shopify_json",
    "origin": "https://www.urbansole.com.pk",
    "all_products_url": "https://www.urbansole.com.pk/collections/all",
    "api_url": "https://www.urbansole.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
