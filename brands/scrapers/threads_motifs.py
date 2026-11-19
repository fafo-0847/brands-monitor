"""Threads & Motifs scraper.

Website: https://www.threadsandmotifs.com
All products: https://www.threadsandmotifs.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "Threads & Motifs",
    "slug": "threads-motifs",
    "website": "https://www.threadsandmotifs.com",
    "strategy": "shopify_json",
    "origin": "https://www.threadsandmotifs.com",
    "all_products_url": "https://www.threadsandmotifs.com/collections/all",
    "api_url": "https://www.threadsandmotifs.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
