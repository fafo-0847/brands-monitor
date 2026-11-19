"""Mushq scraper.

Website: https://mushq.pk
All products: None
Strategy: unavailable
Unavailable: Shopify returns HTTP 423 "This store is unavailable".
"""
from brands.engine import run

CONFIG = {
    "name": "Mushq",
    "slug": "mushq",
    "website": "https://mushq.pk",
    "strategy": "unavailable",
    "origin": "https://mushq.pk",
    "all_products_url": None,
    "reason": "Shopify returns HTTP 423 \"This store is unavailable\"."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
