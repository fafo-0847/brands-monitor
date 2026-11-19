"""Mango scraper.

Website: https://shop.mango.com/pk
All products: https://shop.mango.com/sitemap.xml
Strategy: sitemap_jsonld
Note: Global Mango site: sitemap + JSON-LD for the PK store (heavy bot protection; may fail).
"""
from brands.engine import run

CONFIG = {
    "name": "Mango",
    "slug": "mango",
    "website": "https://shop.mango.com/pk",
    "strategy": "sitemap_jsonld",
    "origin": "https://shop.mango.com",
    "all_products_url": "https://shop.mango.com/sitemap.xml",
    "sitemaps": [
        "https://shop.mango.com/sitemap.xml"
    ],
    "url_pattern": "/pk/en/p/",
    "sitemap_pattern": "pk.*(product|prod)|product.*pk",
    "note": "Global Mango site: sitemap + JSON-LD for the PK store (heavy bot protection; may fail)."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
