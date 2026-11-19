"""Khushposh and Outfitters public catalog monitor."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit
from decimal import Decimal

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

@dataclass(frozen=True)
class Store:
    name: str
    origin: str
    collection_path: str
    requires_total: bool = True

    @property
    def source(self):
        return self.origin + self.collection_path

    @property
    def collection_url(self):
        return self.source + '?sort_by=created-ascending'


KHUSHPOSH = Store('Khushposh', 'https://www.khushposh.co', '/collections/all')
OUTFITTERS = Store('Outfitters', 'https://outfitters.com.pk', '/collections/men-view-all-collection', requires_total=False)
STORES = {'khushposh': KHUSHPOSH, 'outfitters': OUTFITTERS}
BASE = KHUSHPOSH.origin
COLLECTION = KHUSHPOSH.collection_url
SCHEMA = 1


def request_options():
    # Playwright does not automatically use the usual HTTP proxy variables.
    proxy = os.environ.get('MONITOR_PROXY') or os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    return {'proxy': {'server': proxy}} if proxy else {}


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def get(request, url, *, as_json=False, allow_404=False):
    """Bounded retries; never treat an HTTP error as an empty catalog."""
    response = request.get(url, timeout=45000)
    if response.status == 404 and allow_404:
        return None
    for attempt in range(4):
        response = None
        try:
            response = request.get(url, timeout=45000)
            if response.status == 429 or response.status >= 500:
                raise RuntimeError(f'Transient HTTP {response.status}: {url}')
            if not response.ok:
                raise ValueError(f'HTTP {response.status}: {url}')
            return response.json() if as_json else response.text()
        except ValueError:
            raise
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
        finally:
            if response is not None:
                response.dispose()


def parse_collection(markup, page_url, store=KHUSHPOSH):
    soup = BeautifulSoup(markup, 'html.parser')
    grid = soup.select_one('#product-grid')
    if grid is None:
        raise ValueError('Collection product grid missing; refusing to save state')
    handles = set()
    for link in grid.select('a[href]'):
        parts = urlsplit(urljoin(page_url, link['href']))
        if parts.netloc != urlsplit(store.origin).netloc:
            continue
        match = re.fullmatch(rf'(?:{re.escape(store.collection_path)})?/products/([^/]+)', parts.path)
        if match:
            handles.add(match[1])
    if not handles:
        raise ValueError('Collection page has no products; refusing to save state')
    if store == OUTFITTERS and any(not card.select_one('a[href*="/products/"]') for card in grid.find_all('li', recursive=False)):
        raise ValueError('Outfitters grid contains an article card without a product link')
    next_link = soup.select_one('[data-kp-next], a[rel="next"], .pagination a[aria-label="Next page"], #AjaxinatePagination a[href]')
    next_url = urljoin(page_url, next_link['href']) if next_link else None
    if next_url:
        parts = urlsplit(next_url)
        if parts.scheme != 'https' or parts.netloc != urlsplit(store.origin).netloc or parts.path != store.collection_path:
            raise ValueError(f'Unexpected pagination URL: {next_url}')
        if store == OUTFITTERS:
            page = int(parse_qs(urlsplit(page_url).query).get('page', ['1'])[0])
            if parse_qs(parts.query).get('page') != [str(page + 1)]:
                raise ValueError(f'Outfitters pagination skipped a page: {next_url}')
    total_node = soup.select_one('[data-kp-total]')
    total = int(total_node['data-kp-total']) if total_node else None
    if total is None:
        count = soup.select_one('#ProductCountDesktop, #ProductCount')
        if count:
            match = re.fullmatch(r'\s*([\d,]+) products\s*', count.get_text(' ', strip=True))
            if match:
                total = int(match[1].replace(',', ''))
    return handles, next_url, total


def catalog_handles(request, pause, store=KHUSHPOSH):
    url, seen, handles, total = store.collection_url, set(), set(), None
    while url:
        if url in seen or len(seen) >= 100:
            raise ValueError('Pagination loop or page limit reached')
        seen.add(url)
        print(f'{store.name}: reading collection page {len(seen)}', flush=True)
        found, next_url, page_total = parse_collection(get(request, url), url, store)
        if page_total is not None:
            if total is not None and page_total != total:
                raise ValueError('Catalog changed during pagination; retry on next run')
            total = page_total
        if handles.intersection(found):
            raise ValueError('Products repeated across pages; refusing incomplete scan')
        handles.update(found)
        url = next_url
        time.sleep(pause)
    if (total is None and store.requires_total) or (total is not None and len(handles) != total):
        raise ValueError(f'Catalog completeness check failed: found {len(handles)}, expected {total}')
    return handles


def normalize_product(raw, store=KHUSHPOSH):
    pid = str(raw['id'])
    if not pid.isdigit() or not raw['title'] or not raw['handle']:
        raise ValueError('Invalid product identity')
    variants = {}
    for item in raw['variants']:
        vid = str(item['id'])
        if not vid.isdigit() or vid in variants or type(item['available']) is not bool:
            raise ValueError(f'Invalid/duplicate variant in {pid}')
        for field in ('price', 'compare_at_price'):
            price = item.get(field)
            if (price is None and field == 'price') or (price is not None and (type(price) is not int or price < 0)):
                raise ValueError(f'Invalid {field} in {pid}/{vid}')
        variants[vid] = {
            'id': vid, 'title': item['title'], 'options': item['options'],
            'sku': item.get('sku'), 'available': item['available'],
            'price': item['price'], 'compare_at_price': item.get('compare_at_price'),
        }
    if not variants:
        raise ValueError(f'No variants returned for {pid}')
    tags = raw.get('tags', [])
    if isinstance(tags, str):
        tags = [x.strip() for x in tags.split(',')]
    return {
        'id': pid, 'title': raw['title'], 'handle': raw['handle'],
        'url': store.origin + '/products/' + raw['handle'],
        'vendor': raw.get('vendor'), 'type': raw.get('type'),
        'description': raw.get('description'), 'tags': sorted(tags),
        'images': sorted(raw.get('images', [])), 'options': raw.get('options'),
        'available': any(v['available'] for v in variants.values()), 'variants': variants,
    }

def scan_collection_batch(request, pause, store, currency):
    products = {}
    handles = set()
    limit = 250

    for page in range(1, 101):
        url = f'{store.source}/products.json?limit={limit}&page={page}'
        batch = get(request, url, as_json=True)['products']

        for raw in batch:
            variants = []
            for variant in raw['variants']:
                compare_at = variant.get('compare_at_price')
                variants.append({
                    **variant,
                    'price': int(Decimal(variant['price']) * 100),
                    'compare_at_price': (
                        int(Decimal(compare_at) * 100)
                        if compare_at is not None else None
                    ),
                    'options': [
                        variant[key] for key in ('option1', 'option2', 'option3')
                        if variant.get(key) is not None
                    ],
                })

            product = normalize_product({
                **raw,
                'description': raw.get('body_html'),
                'type': raw.get('product_type'),
                'images': [
                    image['src'].removeprefix('https:') for image in raw['images']
                ],
                'variants': variants,
            }, store)

            if product['id'] in products or product['handle'] in handles:
                raise ValueError(f'Duplicate Outfitters product on page {page}')

            products[product['id']] = product
            handles.add(product['handle'])

        if len(batch) < limit:
            break
        time.sleep(pause)
    else:
        raise ValueError('Outfitters collection exceeded the pagination limit')

    if not products:
        raise ValueError('Outfitters returned an empty catalog')

    return {
        'schema_version': SCHEMA,
        'source': store.source,
        'currency': currency,
        'price_unit': 'minor_units',
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'products': products,
    }

def scan(request, pause=0.35, store=KHUSHPOSH, old=None):
    # Force the Pakistani market; fail rather than compare different currencies.
    currency = get(request, store.origin + '/cart.js', as_json=True)['currency']
    if currency != 'PKR':
        raise ValueError(f'Expected PKR, received {currency}; refusing mixed-market comparison')
    if store in (KHUSHPOSH, OUTFITTERS):
        return scan_collection_batch(request, pause, store, currency)
    handles = catalog_handles(request, pause, store)
    print(f'Catalog complete: {len(handles)} products. Fetching size and price data.', flush=True)
    products = {}
    previous_by_handle = {
        product['handle']: product
        for product in (old or {}).get('products', {}).values()
    }
    skipped_handles = set()
    for index, handle in enumerate(sorted(handles), 1):
        url = store.origin + '/products/' + handle + '.js'
        raw = get(request, url, as_json=True, allow_404=True)
        if raw is None:
            print(f'{store.name}: skipping {handle} (HTTP 404)', flush=True)
            skipped_handles.add(handle)
            time.sleep(pause)
            continue
        product = normalize_product(raw, store)
        if product['handle'] != handle or product['id'] in products:
            raise ValueError('Product handle mismatch or duplicate ID')
        products[product['id']] = product
        if index % 20 == 0:
            print(f'Fetched {index}/{len(handles)} products', flush=True)
        time.sleep(pause)
    # Detect additions/removals while product details were being fetched.
    print('Verifying collection membership again.', flush=True)
    final_handles = catalog_handles(request, pause, store)
    if final_handles - skipped_handles != handles - skipped_handles:
        raise ValueError('Catalog membership changed during scan; retry on next run')

    for handle in skipped_handles & final_handles:
        previous = previous_by_handle.get(handle)
        if previous is not None:
            products.setdefault(previous['id'], previous)

    if not products:
        raise ValueError('No product records available; baseline preserved')
    
    return {'schema_version': SCHEMA, 'source': store.source,
            'currency': currency, 'price_unit': 'minor_units',
            'checked_at': datetime.now(timezone.utc).isoformat(), 'products': products}


def money(value, currency):
    return '—' if value is None else f'{currency} {value / 100:,.2f}'


def changes_between(old, new):
    changes = []
    currency = new['currency']

    def add(product, kind, detail, variant=None):
        changes.append({'product_id': product['id'], 'title': product['title'],
                        'url': product['url'] + (f'?variant={variant}' if variant else ''),
                        'kind': kind, 'detail': detail})

    before, after = old['products'], new['products']
    for pid in sorted(before.keys() | after.keys()):
        if pid not in after:
            add(before[pid], 'Product removed', 'No longer listed in the collection')
            continue
        p = after[pid]
        if pid not in before:
            variants = p['variants'].values()
            sizes = ', '.join(v['title'] for v in variants if v['available']) or 'None'
            prices = [v['price'] for v in p['variants'].values()]
            price = money(min(prices), currency)
            if min(prices) != max(prices):
                price += ' – ' + money(max(prices), currency)
            add(p, 'New product', f'Price: {price}; available sizes/options: {sizes}')
            continue
        prior = before[pid]
        for field in ('title', 'handle', 'vendor', 'type', 'description', 'tags', 'images', 'options'):
            if prior[field] != p[field]:
                if field in ('description', 'images', 'options'):
                    detail = f'{field.capitalize()} changed (see changes.json for full before/after)'
                else:
                    detail = f'{field}: {prior[field]} → {p[field]}'
                add(p, 'Product updated', detail)
                changes[-1].update(field=field, before=prior[field], after=p[field])
        a, b = prior['variants'], p['variants']
        for vid in sorted(a.keys() | b.keys()):
            if vid not in b:
                add(p, 'Size/option removed', a[vid]['title'], vid)
                continue
            v = b[vid]
            label = v['title']
            if vid not in a:
                add(p, 'Size/option added', f'{label}: {"Available" if v["available"] else "Unavailable"}, {money(v["price"], currency)}', vid)
                continue
            prev = a[vid]
            if prev['available'] != v['available']:
                add(p, 'Back in stock' if v['available'] else 'Sold out', label, vid)
            for field in ('price', 'compare_at_price'):
                if prev[field] != v[field]:
                    direction = 'changed'
                    if prev[field] is not None and v[field] is not None:
                        direction = 'decreased' if v[field] < prev[field] else 'increased'
                    prefix = 'Price' if field == 'price' else 'Compare-at price'
                    add(p, f'{prefix} {direction}', f'{label}: {money(prev[field], currency)} → {money(v[field], currency)}', vid)
            for field in ('title', 'options', 'sku'):
                if prev[field] != v[field]:
                    add(p, 'Size/option updated', f'{label} {field}: {prev[field]} → {v[field]}', vid)
    return changes


def email_body(changes, store=KHUSHPOSH):
    esc = lambda value: html.escape(str(value), quote=True)
    rows = ''.join(
        '<tr>' + ''.join(f'<td style="border:1px solid #ddd;padding:10px">{cell}</td>' for cell in (
            f'<a href="{esc(c["url"])}">{esc(c["title"])}</a><br><small>ID: {esc(c["product_id"])}</small>',
            esc(c['kind']), esc(c['detail']))) + '</tr>' for c in changes)
    return (f'<html><body style="font-family:Arial,sans-serif"><h2>{esc(store.name)} changes</h2>'
            '<p>Changes since the previous successful check. Prices are in PKR.</p>'
            '<table style="border-collapse:collapse;width:100%"><thead><tr>'
            '<th>Article</th><th>Change</th><th>Details</th></tr></thead><tbody>' + rows +
            '</tbody></table></body></html>')


def notify(playwright, changes, event_key, store=KHUSHPOSH):
    required = {k: os.environ.get(k, '').strip() for k in ('RESEND_API_KEY', 'EMAIL_FROM', 'EMAIL_TO')}
    if not all(required.values()):
        raise ValueError('Set RESEND_API_KEY, EMAIL_FROM and EMAIL_TO before sending')
    recipients = [x.strip() for x in required['EMAIL_TO'].split(',') if x.strip()]
    if not recipients:
        raise ValueError('EMAIL_TO must contain at least one address')
    api = playwright.request.new_context(**request_options(), extra_http_headers={
        'Authorization': 'Bearer ' + required['RESEND_API_KEY']})
    try:
        chunks = [changes[i:i + 60] for i in range(0, len(changes), 60)]
        for index, chunk in enumerate(chunks, 1):
            payload = {'from': required['EMAIL_FROM'], 'to': recipients,
                       'subject': f'{store.name}: {len(changes)} changes ({index}/{len(chunks)})',
                       'html': email_body(chunk, store),
                       'text': '\n\n'.join(f'{c["title"]}: {c["kind"]}\n{c["detail"]}\n{c["url"]}' for c in chunk)}
            # Stable key retries the SAME payload after send/save/push failures.
            key = store.name.lower() + '-' + fingerprint([event_key, payload])
            for attempt in range(4):
                response = None
                try:
                    response = api.post('https://api.resend.com/emails', data=payload,
                                        headers={'Idempotency-Key': key}, timeout=45000)
                    if not response.ok:
                        try:
                            detail = response.json().get('message', 'No error message')
                        except ValueError:
                            detail = 'Non-JSON response'
                        raise ValueError(
                            f'Resend rejected email: HTTP {response.status} — {detail}'
                        )
                    if not response.ok:
                        raise ValueError(f'Resend rejected email: HTTP {response.status}')
                    if not response.json().get('id'):
                        raise ValueError('Resend returned no email ID')
                    break
                except ValueError:
                    raise
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(2 ** (attempt + 1))
                finally:
                    if response is not None:
                        response.dispose()
            time.sleep(0.6)
    finally:
        api.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', choices=STORES, default='khushposh')
    parser.add_argument('--state', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--dry-run', action='store_true', help='Scan and write preview files; do not send or update baseline')
    parser.add_argument('--email-on-first-run', action='store_true', help='Email all products as new on initial run')
    parser.add_argument('--pause', type=float, default=0.35)
    args = parser.parse_args()
    if args.pause < 0:
        parser.error('--pause must be nonnegative')
    store = STORES[args.store]
    data_dir = Path('data') if store == KHUSHPOSH else Path('data') / args.store
    args.state = args.state or data_dir / 'state.json'
    args.report = args.report or data_dir / 'changes.json'
    old = json.loads(args.state.read_text(encoding='utf-8')) if args.state.exists() else None
    if old is not None and (old.get('schema_version') != SCHEMA or not old.get('products') or old.get('source') != store.source):
        raise ValueError('Invalid or incompatible baseline; inspect it before proceeding')
    with sync_playwright() as playwright:
        request = playwright.request.new_context(**request_options(), user_agent=f'{store.name}StockMonitor/1.0',
                                                  extra_http_headers={'Cache-Control': 'no-cache'},
                                                  storage_state={'cookies': [{'name': 'localization', 'value': 'PK',
                                                                             'domain': urlsplit(store.origin).hostname, 'path': '/', 'expires': -1,
                                                                             'httpOnly': False, 'secure': True, 'sameSite': 'Lax'}],
                                                                 'origins': []})
        try:
            current = scan(request, args.pause, store, old=old)
        finally:
            request.dispose()
        if old and current['currency'] != old['currency']:
            raise ValueError('Currency changed; baseline preserved')
        changes = changes_between(old or {'products': {}}, current) if old or args.email_on_first_run else []
        report = {'checked_at': current['checked_at'], 'baseline_created': old is None,
                  'product_count': len(current['products']), 'change_count': len(changes), 'changes': changes}
        if args.dry_run:
            atomic_json(args.state.with_name('preview-state.json'), current)
            atomic_json(args.report.with_name('preview-changes.json'), report)
            preview = args.report.with_name('preview-email.html')
            preview.write_text(email_body(changes, store), encoding='utf-8')
            print(f'Dry run: {report["product_count"]} products, {len(changes)} changes. Baseline unchanged.')
            return
        if changes:
            notify(playwright, changes, fingerprint([old.get('checked_at') if old else 'initial-baseline',
                                                    old['products'] if old else {}, current['products']]), store)
        # Never advance the baseline until every notification is accepted.
        atomic_json(args.report, report)
        atomic_json(args.state, current)
        print(f'Saved {len(current["products"])} products; {len(changes)} changes. ' +
              ('Baseline created.' if old is None else 'Check complete.'))


if __name__ == '__main__':
    main()
