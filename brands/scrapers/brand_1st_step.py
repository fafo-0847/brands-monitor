"""1st Step scraper.

Website: https://1ststep.pk
All products: https://1ststep.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "1st Step",
    "slug": "1st-step",
    "website": "https://1ststep.pk",
    "strategy": "shopify_json",
    "origin": "https://1ststep.pk",
    "all_products_url": "https://1ststep.pk/collections/all",
    "api_url": "https://1ststep.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
