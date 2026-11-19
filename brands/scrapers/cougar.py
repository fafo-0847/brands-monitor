"""Cougar scraper.

Website: https://cougar.com.pk
All products: https://cougar.com.pk/sitemap.xml
Strategy: sitemap_jsonld
Note: Shopify Hydrogen (headless): its listings carry no stock data, so sitemap + product JSON-LD.
"""
from brands.engine import run

CONFIG = {
    "name": "Cougar",
    "slug": "cougar",
    "website": "https://cougar.com.pk",
    "strategy": "sitemap_jsonld",
    "origin": "https://cougar.com.pk",
    "all_products_url": "https://cougar.com.pk/sitemap.xml",
    "sitemaps": [
        "https://cougar.com.pk/sitemap.xml"
    ],
    "note": "Shopify Hydrogen (headless): its listings carry no stock data, so sitemap + product JSON-LD."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
