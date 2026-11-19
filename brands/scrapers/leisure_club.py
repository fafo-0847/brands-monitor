"""Leisure Club scraper.

Website: https://leisureclub.pk
All products: None
Strategy: unavailable
Unavailable: Shopify store publishes no products (products.json and sitemap empty).
"""
from brands.engine import run

CONFIG = {
    "name": "Leisure Club",
    "slug": "leisure-club",
    "website": "https://leisureclub.pk",
    "strategy": "unavailable",
    "origin": "https://www.leisureclub.pk",
    "all_products_url": None,
    "reason": "Shopify store publishes no products (products.json and sitemap empty)."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
