"""Maria B scraper.

Website: https://www.mariab.pk
All products: https://www.mariab.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Maria B",
    "slug": "maria-b",
    "website": "https://www.mariab.pk",
    "strategy": "shopify_json",
    "origin": "https://www.mariab.pk",
    "all_products_url": "https://www.mariab.pk/collections/all",
    "api_url": "https://www.mariab.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
