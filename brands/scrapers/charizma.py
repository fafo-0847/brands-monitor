"""Charizma scraper.

Website: https://charizma.pk
All products: None
Strategy: unavailable
Unavailable: Domain charizma.pk does not resolve (DNS failure).
"""
from brands.engine import run

CONFIG = {
    "name": "Charizma",
    "slug": "charizma",
    "website": "https://charizma.pk",
    "strategy": "unavailable",
    "origin": "https://charizma.pk",
    "all_products_url": None,
    "reason": "Domain charizma.pk does not resolve (DNS failure)."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
