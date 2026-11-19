"""OnlineThriftStore.pk scraper.

Website: https://onlinethriftstore.pk
All products: https://onlinethriftstore.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "OnlineThriftStore.pk",
    "slug": "onlinethriftstore-pk",
    "website": "https://onlinethriftstore.pk",
    "strategy": "shopify_json",
    "origin": "https://onlinethriftstore.pk",
    "all_products_url": "https://onlinethriftstore.pk/collections/all",
    "api_url": "https://onlinethriftstore.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
