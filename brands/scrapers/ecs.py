"""ECS scraper.

Website: https://www.ecs.com.pk
All products: None
Strategy: unavailable
Unavailable: WordPress site without a product catalog (no WooCommerce, no product sitemap).
"""
from brands.engine import run

CONFIG = {
    "name": "ECS",
    "slug": "ecs",
    "website": "https://www.ecs.com.pk",
    "strategy": "unavailable",
    "origin": "https://ecs.com.pk",
    "all_products_url": None,
    "reason": "WordPress site without a product catalog (no WooCommerce, no product sitemap)."
}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
