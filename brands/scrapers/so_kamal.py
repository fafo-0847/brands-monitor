"""So Kamal scraper.

Website: https://sokamal.com
All products: https://www.sokamal.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "So Kamal",
    "slug": "so-kamal",
    "website": "https://sokamal.com",
    "strategy": "shopify_json",
    "origin": "https://www.sokamal.com",
    "all_products_url": "https://www.sokamal.com/collections/all",
    "api_url": "https://www.sokamal.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
