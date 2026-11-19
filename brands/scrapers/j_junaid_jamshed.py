"""J. (Junaid Jamshed) scraper.

Website: https://www.junaidjamshed.com
All products: https://www.junaidjamshed.com/collections/all
Strategy: shopify_json
"""
from brands.engine import run

CONFIG = {
    "name": "J. (Junaid Jamshed)",
    "slug": "j-junaid-jamshed",
    "website": "https://www.junaidjamshed.com",
    "strategy": "shopify_json",
    "origin": "https://www.junaidjamshed.com",
    "all_products_url": "https://www.junaidjamshed.com/collections/all",
    "api_url": "https://www.junaidjamshed.com/collections/all/products.json"
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
