"""Metro scraper.

Website: https://www.metroshoes.com.pk
All products: None
Strategy: unavailable
Unavailable: Shopify returns HTTP 402 "Store unavailable".
"""
from brands.engine import run

CONFIG = {
    "name": "Metro",
    "slug": "metro",
    "website": "https://www.metroshoes.com.pk",
    "strategy": "unavailable",
    "origin": "https://www.metroshoes.com.pk",
    "all_products_url": None,
    "reason": "Shopify returns HTTP 402 \"Store unavailable\"."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
