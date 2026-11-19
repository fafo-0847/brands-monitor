"""Sapphire scraper.

Website: https://pk.sapphireonline.pk
All products: https://pk.sapphireonline.pk/collections/woman
Strategy: sfcc
Note: Salesforce Commerce Cloud: crawls top-level categories and dedupes by product ID.
"""
from brands.engine import run

CONFIG = {
    "name": "Sapphire",
    "slug": "sapphire",
    "website": "https://pk.sapphireonline.pk",
    "strategy": "sfcc",
    "origin": "https://pk.sapphireonline.pk",
    "all_products_url": "https://pk.sapphireonline.pk/collections/woman",
    "category_urls": [
        "https://pk.sapphireonline.pk/collections/new-in",
        "https://pk.sapphireonline.pk/collections/woman",
        "https://pk.sapphireonline.pk/collections/ready-to-wear",
        "https://pk.sapphireonline.pk/collections/unstitched",
        "https://pk.sapphireonline.pk/collections/western-wear",
        "https://pk.sapphireonline.pk/collections/modest-wear",
        "https://pk.sapphireonline.pk/collections/fragrances",
        "https://pk.sapphireonline.pk/collections/accessories",
        "https://pk.sapphireonline.pk/collections/bags",
        "https://pk.sapphireonline.pk/collections/womens-shoes"
    ],
    "note": "Salesforce Commerce Cloud: crawls top-level categories and dedupes by product ID."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
