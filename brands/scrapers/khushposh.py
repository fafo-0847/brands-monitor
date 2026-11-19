"""Khushposh scraper.

Website: https://www.khushposh.co
All products: https://www.khushposh.co/collections/all
Strategy: monitor_store
Note: Original monitor.py scanner (unchanged); baseline migrated from monitor-state:state.json
"""
from brands.engine import run

CONFIG = {
    "name": "Khushposh",
    "slug": "khushposh",
    "website": "https://www.khushposh.co",
    "strategy": "monitor_store",
    "store": "khushposh",
    "origin": "https://www.khushposh.co",
    "all_products_url": "https://www.khushposh.co/collections/all",
    "legacy_state": "state.json",
    "note": "Original monitor.py scanner (unchanged); baseline migrated from monitor-state:state.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
