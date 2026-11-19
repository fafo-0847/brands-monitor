"""Generation scraper.

Website: https://generation.com.pk
All products: https://generation.com.pk/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Generation",
    "slug": "generation",
    "website": "https://generation.com.pk",
    "strategy": "shopify_json",
    "origin": "https://generation.com.pk",
    "all_products_url": "https://generation.com.pk/collections/all",
    "api_url": "https://generation.com.pk/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
