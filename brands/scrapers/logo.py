"""Logo scraper.

Website: https://www.logoofficial.com
All products: https://www.logoofficial.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Logo",
    "slug": "logo",
    "website": "https://www.logoofficial.com",
    "strategy": "shopify_json",
    "origin": "https://www.logoofficial.com",
    "all_products_url": "https://www.logoofficial.com/collections/all",
    "api_url": "https://www.logoofficial.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
