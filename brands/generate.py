"""Generate one scraper module per brand from registry.json plus manual overrides."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / 'registry.json'
OUT = HERE / 'scrapers'

KHAADI_CATEGORIES = ['/new-in/', '/ready-to-wear/', '/fabrics/', '/accessories/', '/fragrances/', '/home/',
                     '/sale/', '/winter-collection/', '/festive-edit/', '/best-sellers/ready-to-wear-best-sellers/']
SAPPHIRE_CATEGORIES = ['/collections/new-in', '/collections/woman', '/collections/ready-to-wear',
                       '/collections/unstitched', '/collections/western-wear', '/collections/modest-wear',
                       '/collections/fragrances', '/collections/accessories', '/collections/bags',
                       '/collections/womens-shoes']


def sitemap_cfg(origin, sitemap='/sitemap.xml', **extra):
    return {'strategy': 'sitemap_jsonld', 'origin': origin, 'all_products_url': origin + sitemap,
            'sitemaps': [origin + sitemap], **extra}


def hydrogen_cfg(origin):
    return {'strategy': 'hydrogen_listing', 'origin': origin, 'all_products_url': origin + '/collections/all',
            'collection_path': '/collections/all', 'sitemaps': [origin + '/sitemap.xml'],
            'note': 'Shopify Hydrogen (headless): /collections/all listing pages; product pages only to confirm '
                    'unclear stock and for sitemap products missing from the listing.'}


def monitor_cfg(store, origin, collection, legacy_state):
    return {'strategy': 'monitor_store', 'store': store, 'origin': origin,
            'all_products_url': origin + collection, 'legacy_state': legacy_state,
            'note': 'Original monitor.py scanner (unchanged); baseline migrated from monitor-state:' + legacy_state}


# Brands monitored before the CSV import; not in registry.json.
EXTRA_BRANDS = {'khushposh': {'brand': 'Khushposh', 'slug': 'khushposh', 'website': 'https://www.khushposh.co'}}

OVERRIDES = {
    'khushposh': monitor_cfg('khushposh', 'https://www.khushposh.co', '/collections/all', 'state.json'),
    'outfitters': monitor_cfg('outfitters', 'https://outfitters.com.pk', '/collections/men-view-all-collection',
                              'outfitters/state.json'),
    'khaadi': {'strategy': 'sfcc', 'origin': 'https://pk.khaadi.com', 'all_products_url': 'https://pk.khaadi.com/new-in/',
               'category_urls': ['https://pk.khaadi.com' + c for c in KHAADI_CATEGORIES],
               'note': 'Salesforce Commerce Cloud: no all-products page; crawls top-level categories and dedupes by product ID.'},
    'sapphire': {'strategy': 'sfcc', 'origin': 'https://pk.sapphireonline.pk',
                 'all_products_url': 'https://pk.sapphireonline.pk/collections/woman',
                 'category_urls': ['https://pk.sapphireonline.pk' + c for c in SAPPHIRE_CATEGORIES],
                 'note': 'Salesforce Commerce Cloud: crawls top-level categories and dedupes by product ID.'},
    'agha-noor': {'strategy': 'shopify_json', 'origin': 'https://pk.aghanoorofficial.com',
                  'all_products_url': 'https://pk.aghanoorofficial.com/collections/all',
                  'api_url': 'https://pk.aghanoorofficial.com/collections/all/products.json'},
    'breakout': hydrogen_cfg('https://www.breakout.com.pk'),
    'cougar': sitemap_cfg('https://cougar.com.pk', note='Shopify Hydrogen (headless): its listings carry no stock data, so sitemap + product JSON-LD.'),
    'equator': hydrogen_cfg('https://equatorstores.com'),
    'orient-textiles': hydrogen_cfg('https://shopatorient.com'),
    'republic-by-omar-farooq': {'strategy': 'shopify_handles', 'origin': 'https://republicbespoke.com',
                                'all_products_url': 'https://republicbespoke.com/sitemap.xml',
                                'sitemaps': ['https://republicbespoke.com/sitemap.xml'],
                                'min_pause': 1.0,
                                'note': 'products.json is empty; handles from sitemap, details from /products/<handle>.js '
                                        '(~1,600 requests, paced at 1/s to stay under the Shopify 429 limit).'},
    'lama-retail': {'strategy': 'shopify_json', 'origin': 'https://lamaretail.com',
                    'all_products_url': 'https://lamaretail.com/collections/all',
                    'api_url': 'https://lamaretail.com/collections/all/products.json',
                    'pkr_labelled_as': 'SAR',
                    'note': 'Store currency is set to SAR (rate 1.0) but the amounts are PKR.'},
    'bareeze': {'strategy': 'bareeze_listing', 'origin': 'https://bareeze.com',
                'all_products_url': 'https://bareeze.com/all-products',
                'category_sitemap': 'https://www.bareeze.com/sitemap/sitemap_cat_0.xml',
                'skip_categories': ['test', 'lookbook'],
                'note': 'Next.js storefront: every top-level category (2 requests each via its load-more page), deduped by product ID.'},
    'mango': {**sitemap_cfg('https://shop.mango.com', '/sitemap.xml', url_pattern=r'/pk/en/p/', sitemap_pattern=r'pk.*(product|prod)|product.*pk'),
              'note': 'Global Mango site: sitemap + JSON-LD for the PK store (heavy bot protection; may fail).'},
}

UNAVAILABLE = {
    'charizma': 'Domain charizma.pk does not resolve (DNS failure).',
    'mushq': 'Shopify returns HTTP 423 "This store is unavailable".',
    'metro': 'Shopify returns HTTP 402 "Store unavailable".',
    'kayseria': 'Shopify store publishes no products (products.json and sitemap empty).',
    'leisure-club': 'Shopify store publishes no products (products.json and sitemap empty).',
    'ecs': 'WordPress site without a product catalog (no WooCommerce, no product sitemap).',
    'image': 'Homepage is a static landing page; no public product listing found.',
}

TEMPLATE = '''"""{name} scraper.

Website: {website}
All products: {all_products_url}
Strategy: {strategy}{note}
"""
from brands.engine import run

CONFIG = {config}


def scrape(**kwargs):
    return run(CONFIG, **kwargs)
'''


def build(entry):
    slug = entry['slug']
    base = {'name': entry['brand'], 'slug': slug, 'website': entry['website']}
    if slug in UNAVAILABLE:
        return {**base, 'strategy': 'unavailable', 'origin': entry.get('origin') or entry['website'],
                'all_products_url': None, 'reason': UNAVAILABLE[slug]}
    if slug in OVERRIDES:
        return {**base, **OVERRIDES[slug]}
    if entry.get('strategy') == 'shopify_products_json':
        return {**base, 'strategy': 'shopify_json', 'origin': entry['origin'],
                'all_products_url': entry['all_products_url'], 'api_url': entry['api']}
    raise ValueError(f'No scraper rule for {slug}: {entry.get("platform")}/{entry.get("strategy")}')


def main():
    registry = {**EXTRA_BRANDS, **json.loads(REGISTRY.read_text(encoding='utf-8'))}
    OUT.mkdir(exist_ok=True)
    (OUT / '__init__.py').write_text('', encoding='utf-8')
    configs = {}
    for slug, entry in registry.items():
        config = build(entry)
        configs[slug] = config
        note = f'\nNote: {config["note"]}' if config.get('note') else ''
        if config['strategy'] == 'unavailable':
            note = f'\nUnavailable: {config["reason"]}'
        module = slug.replace('-', '_')
        if module[0].isdigit():
            module = 'brand_' + module
        body = TEMPLATE.format(name=config['name'], website=config['website'], strategy=config['strategy'],
                               all_products_url=config.get('all_products_url'), note=note,
                               config=json.dumps(config, indent=4, ensure_ascii=False)
                               .replace(': null', ': None').replace(': true', ': True').replace(': false', ': False'))
        (OUT / f'{module}.py').write_text(body, encoding='utf-8')
        config['module'] = module
    (HERE / 'scrapers.json').write_text(json.dumps(configs, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Generated {len(configs)} scraper modules in {OUT}')


if __name__ == '__main__':
    main()
