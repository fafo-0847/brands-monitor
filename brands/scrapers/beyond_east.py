"""Beyond East scraper.

Website: https://www.beyondeast.com
All products: https://www.beyondeast.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Beyond East",
    "slug": "beyond-east",
    "website": "https://www.beyondeast.com",
    "strategy": "shopify_json",
    "origin": "https://www.beyondeast.com",
    "all_products_url": "https://www.beyondeast.com/collections/all",
    "api_url": "https://www.beyondeast.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
