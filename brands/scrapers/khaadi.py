"""Khaadi scraper.

Website: https://pk.khaadi.com
All products: https://pk.khaadi.com/new-in/
Strategy: sfcc
Note: Salesforce Commerce Cloud: no all-products page; crawls top-level categories and dedupes by product ID.
"""
from brands.engine import run

CONFIG = {
    "name": "Khaadi",
    "slug": "khaadi",
    "website": "https://pk.khaadi.com",
    "strategy": "sfcc",
    "origin": "https://pk.khaadi.com",
    "all_products_url": "https://pk.khaadi.com/new-in/",
    "category_urls": [
        "https://pk.khaadi.com/new-in/",
        "https://pk.khaadi.com/ready-to-wear/",
        "https://pk.khaadi.com/fabrics/",
        "https://pk.khaadi.com/accessories/",
        "https://pk.khaadi.com/fragrances/",
        "https://pk.khaadi.com/home/",
        "https://pk.khaadi.com/sale/",
        "https://pk.khaadi.com/winter-collection/",
        "https://pk.khaadi.com/festive-edit/",
        "https://pk.khaadi.com/best-sellers/ready-to-wear-best-sellers/"
    ],
    "note": "Salesforce Commerce Cloud: no all-products page; crawls top-level categories and dedupes by product ID."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
