"""Kayseria scraper.

Website: https://www.kayseria.com
All products: None
Strategy: unavailable
Unavailable: Shopify store publishes no products (products.json and sitemap empty).
"""
from brands.engine import run

CONFIG = {
    "name": "Kayseria",
    "slug": "kayseria",
    "website": "https://www.kayseria.com",
    "strategy": "unavailable",
    "origin": "https://www.kayseria.com",
    "all_products_url": None,
    "reason": "Shopify store publishes no products (products.json and sitemap empty)."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
