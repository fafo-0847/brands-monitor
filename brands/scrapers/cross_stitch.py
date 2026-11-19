"""Cross Stitch scraper.

Website: https://www.crossstitch.pk
All products: https://crossstitch.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Cross Stitch",
    "slug": "cross-stitch",
    "website": "https://www.crossstitch.pk",
    "strategy": "shopify_json",
    "origin": "https://crossstitch.pk",
    "all_products_url": "https://crossstitch.pk/collections/all",
    "api_url": "https://crossstitch.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
