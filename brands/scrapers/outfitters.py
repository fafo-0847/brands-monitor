"""Outfitters scraper.

Website: https://outfitters.com.pk
All products: https://outfitters.com.pk/collections/men-view-all-collection
Strategy: monitor_store
Note: Original monitor.py scanner (unchanged); baseline migrated from monitor-state:outfitters/state.json
"""
from brands.engine import run

CONFIG = {
    "name": "Outfitters",
    "slug": "outfitters",
    "website": "https://outfitters.com.pk",
    "strategy": "monitor_store",
    "store": "outfitters",
    "origin": "https://outfitters.com.pk",
    "all_products_url": "https://outfitters.com.pk/collections/men-view-all-collection",
    "legacy_state": "outfitters/state.json",
    "note": "Original monitor.py scanner (unchanged); baseline migrated from monitor-state:outfitters/state.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
