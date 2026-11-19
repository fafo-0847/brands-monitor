"""Lama Retail scraper.

Website: https://lamaretail.com
All products: https://lamaretail.com/collections/all
Strategy: shopify_json
Note: Store currency is set to SAR (rate 1.0) but the amounts are PKR.
"""
from brands.engine import run

CONFIG = {
    "name": "Lama Retail",
    "slug": "lama-retail",
    "website": "https://lamaretail.com",
    "strategy": "shopify_json",
    "origin": "https://lamaretail.com",
    "all_products_url": "https://lamaretail.com/collections/all",
    "api_url": "https://lamaretail.com/collections/all/products.json",
    "pkr_labelled_as": "SAR",
    "note": "Store currency is set to SAR (rate 1.0) but the amounts are PKR."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
