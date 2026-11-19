"""Probe each brand: save raw HTML, detect platform, find the all-products listing."""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / 'Pakistan Fashion Brands - Brands.csv'
RAW_DIR = ROOT / 'raw_html'
REGISTRY = Path(__file__).resolve().parent / 'registry.json'
LOG = ROOT / 'logs' / 'probe.log'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0 Safari/537.36')
TIMEOUT = 15
ALL_LINK_TEXT = re.compile(r'\b(shop all|view all|all products|see all|shop now|new arrivals?)\b', re.I)


def slugify(name):
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug


def log(message):
    line = f'{time.strftime("%H:%M:%S")} {message}'
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as fh:
        fh.write(line + '\n')


class Fetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9'})

    def get(self, url, accept=None):
        headers = {'Accept': accept} if accept else {}
        try:
            response = self.session.get(url, timeout=TIMEOUT, headers=headers, allow_redirects=True)
            if response.status_code in (403, 503, 429) and accept is None:
                return self.curl(url) or (response.status_code, response.url, response.text)
            return response.status_code, response.url, response.text
        except requests.RequestException as exc:
            fallback = self.curl(url)
            if fallback:
                return fallback
            return None, url, f'ERROR: {type(exc).__name__}: {exc}'

    def curl(self, url):
        command = ['curl', '-sSL', '--compressed', '-m', str(TIMEOUT), '-A', UA,
                   '-w', '\n__STATUS__%{http_code} %{url_effective}', url]
        try:
            out = subprocess.run(command, capture_output=True, timeout=TIMEOUT + 5).stdout.decode('utf-8', 'replace')
        except (subprocess.TimeoutExpired, OSError):
            return None
        body, _, tail = out.rpartition('\n__STATUS__')
        parts = tail.split(' ', 1)
        if not parts[0].isdigit() or parts[0] == '000':
            return None
        return int(parts[0]), parts[1] if len(parts) > 1 else url, body

    def json(self, url):
        status, final, body = self.get(url, accept='application/json')
        if status != 200:
            return None
        try:
            return json.loads(body)
        except ValueError:
            return None


def detect_platform(html):
    lower = html.lower()
    if 'cdn.shopify.com' in lower or 'shopify.theme' in lower:
        return 'shopify'
    if 'woocommerce' in lower or 'wp-content/plugins/woocommerce' in lower:
        return 'woocommerce'
    if 'demandware' in lower or '/on/demandware.static/' in lower:
        return 'sfcc'
    if 'mage/cookies' in lower or 'magento' in lower or 'mage-init' in lower:
        return 'magento'
    if 'wp-content' in lower:
        return 'wordpress'
    return 'unknown'


def save(folder, name, body):
    path = folder / name
    path.write_text(body, encoding='utf-8')
    return path.name


def nav_candidates(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    host = urlsplit(base).netloc
    found = []
    for link in soup.select('a[href]'):
        text = link.get_text(' ', strip=True)
        href = urljoin(base, link['href'])
        if urlsplit(href).netloc != host:
            continue
        if ALL_LINK_TEXT.search(text) or re.search(r'/(collections/all|shop|view-all|all-products)\b', href, re.I):
            if href not in found:
                found.append(href)
    return found[:15]


def sitemap_product_urls(fetcher, origin):
    candidates = []
    status, _, robots = fetcher.get(origin + '/robots.txt')
    if status == 200:
        candidates += re.findall(r'(?im)^\s*sitemap:\s*(\S+)', robots)
    candidates += [origin + '/sitemap.xml', origin + '/sitemap_index.xml']
    seen = set()
    for sitemap in candidates:
        if sitemap in seen:
            continue
        seen.add(sitemap)
        status, _, body = fetcher.get(sitemap)
        if status != 200 or '<' not in body:
            continue
        locs = re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', body)
        product_maps = [u for u in locs if re.search(r'product', u, re.I) and u.endswith('.xml')]
        if product_maps:
            status, _, body = fetcher.get(product_maps[0])
            if status == 200:
                urls = re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', body)
                return sitemap, product_maps, [u for u in urls if not u.endswith(('.jpg', '.png', '.webp'))]
        product_like = [u for u in locs if re.search(r'/(product|products|p)/|\.html$', u)]
        if product_like:
            return sitemap, [sitemap], product_like
    return None, [], []


def probe_shopify(fetcher, origin, folder, result):
    cart = fetcher.json(origin + '/cart.js')
    result['currency'] = cart.get('currency') if isinstance(cart, dict) else None
    for path in ('/collections/all', '/products'):
        data = fetcher.json(origin + path + ('/products.json?limit=250' if path != '/products' else '.json?limit=250'))
        if data and data.get('products') is not None:
            result['all_products_url'] = origin + path
            result['api'] = origin + path + ('/products.json' if path != '/products' else '.json')
            result['first_page_count'] = len(data['products'])
            save(folder, 'products_page1.json', json.dumps(data, indent=1))
            break
    status, final, body = fetcher.get(origin + '/collections/all')
    if status == 200:
        save(folder, 'collections_all.html', body)
        count = re.search(r'([\d,]+)\s+products', BeautifulSoup(body, 'html.parser').get_text(' '))
        if count:
            result['listed_total'] = int(count[1].replace(',', ''))
    result['strategy'] = 'shopify_products_json' if result.get('api') else 'shopify_handles'


def probe_woocommerce(fetcher, origin, folder, result):
    data = fetcher.json(origin + '/wp-json/wc/store/v1/products?per_page=100')
    if isinstance(data, list):
        result['api'] = origin + '/wp-json/wc/store/v1/products'
        result['first_page_count'] = len(data)
        save(folder, 'products_page1.json', json.dumps(data, indent=1))
        result['strategy'] = 'woocommerce_store_api'
    for path in ('/shop/', '/shop'):
        status, final, body = fetcher.get(origin + path)
        if status == 200:
            save(folder, 'shop.html', body)
            result['all_products_url'] = final
            break


def probe_brand(fetcher, row):
    name, website = row['Brand'].strip(), row['Website'].strip()
    slug = slugify(name)
    folder = RAW_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)
    result = {'brand': name, 'slug': slug, 'website': website, 'category': row['Category'],
              'status': 'ok', 'saved': []}
    status, final, html = fetcher.get(website)
    result['home_status'] = status
    if status is None or status >= 400 or len(html) < 500:
        result['status'] = 'unreachable' if status is None else f'http_{status}'
        result['error'] = html[:200] if status is None else None
        if html:
            result['saved'].append(save(folder, 'homepage.html', html))
        return result
    result['saved'].append(save(folder, 'homepage.html', html))
    parts = urlsplit(final)
    origin = f'{parts.scheme}://{parts.netloc}'
    result['origin'] = origin
    platform = detect_platform(html)
    if platform != 'shopify':
        probe = fetcher.json(origin + '/products.json?limit=1')
        if probe and 'products' in probe:
            platform = 'shopify'
    result['platform'] = platform
    result['nav_candidates'] = nav_candidates(html, final)
    if platform == 'shopify':
        probe_shopify(fetcher, origin, folder, result)
    elif platform in ('woocommerce', 'wordpress'):
        probe_woocommerce(fetcher, origin, folder, result)
    if not result.get('strategy'):
        sitemap, maps, urls = sitemap_product_urls(fetcher, origin)
        if urls:
            result['strategy'] = 'sitemap_jsonld'
            result['sitemap'] = sitemap
            result['product_sitemaps'] = maps[:20]
            result['sitemap_product_count'] = len(urls)
            save(folder, 'sitemap_products.txt', '\n'.join(urls))
            status, _, body = fetcher.get(urls[0])
            if status == 200:
                result['saved'].append(save(folder, 'sample_product.html', body))
        else:
            result['strategy'] = 'listing_pages'
        if not result.get('all_products_url') and result['nav_candidates']:
            result['all_products_url'] = result['nav_candidates'][0]
            status, _, body = fetcher.get(result['all_products_url'])
            if status == 200:
                result['saved'].append(save(folder, 'listing.html', body))
    result['saved'] = sorted(set(result['saved']) | {p.name for p in folder.iterdir()})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=10 ** 6)
    parser.add_argument('--only', nargs='*')
    args = parser.parse_args()
    rows = [r for r in csv.DictReader(CSV_PATH.open(encoding='utf-8-sig')) if r.get('Brand')]
    registry = json.loads(REGISTRY.read_text(encoding='utf-8')) if REGISTRY.exists() else {}
    fetcher = Fetcher()
    total = len(rows)
    for index, row in enumerate(rows, 1):
        if index < args.start or index > args.end:
            continue
        if args.only and slugify(row['Brand']) not in args.only:
            continue
        tag = f'[{index:02d}/{total}] {row["Brand"]}'
        log(f'{tag} ... in progress')
        started = time.time()
        try:
            result = probe_brand(fetcher, row)
        except Exception as exc:
            result = {'brand': row['Brand'], 'slug': slugify(row['Brand']), 'website': row['Website'],
                      'status': 'error', 'error': f'{type(exc).__name__}: {exc}'}
        result['probed_seconds'] = round(time.time() - started, 1)
        registry[result['slug']] = result
        REGISTRY.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding='utf-8')
        summary = (f'platform={result.get("platform", "-")} strategy={result.get("strategy", "-")} '
                   f'all={result.get("all_products_url", "-")} '
                   f'count={result.get("first_page_count", result.get("sitemap_product_count", "-"))}')
        state = 'DONE' if result['status'] == 'ok' else f'ISSUE ({result["status"]})'
        log(f'{tag} {state} {summary} [{result["probed_seconds"]}s]')


if __name__ == '__main__':
    sys.exit(main())
