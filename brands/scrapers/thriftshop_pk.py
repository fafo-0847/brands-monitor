"""ThriftShop.pk scraper.

Website: https://thriftshop.pk
All products: https://thriftshop.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "ThriftShop.pk",
    "slug": "thriftshop-pk",
    "website": "https://thriftshop.pk",
    "strategy": "shopify_json",
    "origin": "https://thriftshop.pk",
    "all_products_url": "https://thriftshop.pk/collections/all",
    "api_url": "https://thriftshop.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
