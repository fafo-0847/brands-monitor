"""Image scraper.

Website: https://image1993.com
All products: None
Strategy: unavailable
Unavailable: Homepage is a static landing page; no public product listing found.
"""
from brands.engine import run

CONFIG = {
    "name": "Image",
    "slug": "image",
    "website": "https://image1993.com",
    "strategy": "unavailable",
    "origin": "https://image1993.com",
    "all_products_url": None,
    "reason": "Homepage is a static landing page; no public product listing found."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
