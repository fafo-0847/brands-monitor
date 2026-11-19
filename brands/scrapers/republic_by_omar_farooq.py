"""Republic by Omar Farooq scraper.

Website: https://republicbyomarfarooq.com
All products: https://republicbespoke.com/sitemap.xml
Strategy: shopify_handles
Note: products.json is empty; handles from sitemap, details from /products/<handle>.js (~1,600 requests, paced at 1/s to stay under the Shopify 429 limit).
"""
from brands.engine import run

CONFIG = {
    "name": "Republic by Omar Farooq",
    "slug": "republic-by-omar-farooq",
    "website": "https://republicbyomarfarooq.com",
    "strategy": "shopify_handles",
    "origin": "https://republicbespoke.com",
    "all_products_url": "https://republicbespoke.com/sitemap.xml",
    "sitemaps": [
        "https://republicbespoke.com/sitemap.xml"
    ],
    "min_pause": 1.0,
    "note": "products.json is empty; handles from sitemap, details from /products/<handle>.js (~1,600 requests, paced at 1/s to stay under the Shopify 429 limit)."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
