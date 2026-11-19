"""Shared scraping strategies for the brand scrapers.

Every strategy returns a snapshot in the same shape as monitor.py, so
monitor.changes_between() can diff any two snapshots of any brand.
"""
from __future__ import annotations

import html
import json
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

SCHEMA = 1
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0 Safari/537.36')


class Unavailable(RuntimeError):
    pass


class Client:
    def __init__(self, origin, pause=0.35, log=print, fail_fast_429=False):
        self.pause = pause
        self.fail_fast_429 = fail_fast_429
        self.requests = 0
        self.log = log
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9',
                                     'Cache-Control': 'no-cache'})
        host = urlsplit(origin).hostname
        self.session.cookies.set('localization', 'PK', domain=host)
        proxy = os.environ.get('MONITOR_PROXY', '').strip()
        if proxy:
            self.session.proxies.update({'http': proxy, 'https': proxy})

    def get(self, url, *, as_json=False, allow_404=False):
        attempts = 6
        for attempt in range(attempts):
            try:
                self.requests += 1
                response = self.session.get(url, timeout=45)
            except requests.RequestException:
                if attempt == attempts - 1:
                    raise
                time.sleep(2 ** (attempt + 1))
                continue
            if response.status_code == 404 and allow_404:
                return None
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == attempts - 1 or (response.status_code == 429 and self.fail_fast_429):
                    raise RuntimeError(f'Transient HTTP {response.status_code}: {url}')
                retry_after = response.headers.get('Retry-After', '')
                wait = min(int(retry_after), 120) if retry_after.isdigit() else min(5 * 2 ** (attempt + 1), 120)
                self.log(f'HTTP {response.status_code}, waiting {wait}s (attempt {attempt + 1}/{attempts})')
                time.sleep(wait)
                continue
            if response.status_code == 403:
                raise ValueError(f'HTTP 403 (site is blocking this IP; set MONITOR_PROXY): {url}')
            if not response.ok:
                raise ValueError(f'HTTP {response.status_code}: {url}')
            time.sleep(self.pause)
            return response.json() if as_json else response.text


def minor_units(value):
    if value is None or value == '':
        return None
    text = re.sub(r'[^\d.]', '', str(value))
    try:
        return int(Decimal(text) * 100)
    except InvalidOperation:
        return None


def product_record(pid, title, url, variants, **extra):
    record = {
        'id': str(pid), 'title': title, 'handle': urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1],
        'url': url, 'vendor': extra.get('vendor'), 'type': extra.get('type'),
        'description': extra.get('description'), 'tags': sorted(extra.get('tags') or []),
        'images': sorted(extra.get('images') or []), 'options': extra.get('options'),
        'variants': variants,
    }
    record['available'] = any(v['available'] for v in variants.values())
    return record


def variant_record(vid, title, price, available, sku=None, compare_at=None, options=None):
    return {'id': str(vid), 'title': title, 'options': options or [title], 'sku': sku,
            'available': bool(available), 'price': price, 'compare_at_price': compare_at}


def snapshot(config, currency, products):
    if not products:
        raise ValueError(f'{config["name"]}: no products found; baseline preserved')
    return {'schema_version': SCHEMA, 'source': config['all_products_url'], 'currency': currency,
            'price_unit': 'minor_units', 'checked_at': datetime.now(timezone.utc).isoformat(),
            'products': products}


def shopify_currency(client, origin, config=None):
    try:
        cart = client.get(origin + '/cart.js', as_json=True)
    except Exception:
        return 'PKR'
    currency = cart.get('currency', 'PKR')
    mislabel = (config or {}).get('pkr_labelled_as')
    if mislabel and currency == mislabel:
        return 'PKR'  # store settings say e.g. SAR at rate 1.0, but the amounts are rupees
    if currency != 'PKR':
        raise ValueError(f'Expected PKR, received {currency}; refusing mixed-market comparison')
    return currency


def normalize_shopify_js(raw, origin):
    variants = {}
    for item in raw['variants']:
        variants[str(item['id'])] = variant_record(
            item['id'], item['title'], item['price'], item['available'], item.get('sku'),
            item.get('compare_at_price'), item.get('options'))
    tags = raw.get('tags', [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    return product_record(raw['id'], raw['title'], origin + '/products/' + raw['handle'], variants,
                          vendor=raw.get('vendor'), type=raw.get('type') or raw.get('product_type'),
                          description=raw.get('description') or raw.get('body_html'), tags=tags,
                          images=[i if isinstance(i, str) else i['src'] for i in raw.get('images', [])],
                          options=raw.get('options'))


def strategy_shopify_json(config, client, limit=None, max_pages=100):
    origin = config['origin']
    currency = shopify_currency(client, origin, config)
    products = {}
    page_size = min(250, limit) if limit else 250
    for page in range(1, max_pages + 1):
        url = f'{config["api_url"]}?limit={page_size}&page={page}'
        batch = client.get(url, as_json=True)['products']
        client.log(f'{config["name"]}: products.json page {page}: {len(batch)} products')
        for raw in batch:
            raw = {**raw, 'variants': [
                {**v, 'price': minor_units(v['price']), 'compare_at_price': minor_units(v.get('compare_at_price')),
                 'options': [v[k] for k in ('option1', 'option2', 'option3') if v.get(k) is not None]}
                for v in raw['variants']]}
            products[str(raw['id'])] = normalize_shopify_js(raw, origin)
            if limit and len(products) >= limit:
                return snapshot(config, currency, products)
        if len(batch) < page_size:
            break
    return snapshot(config, currency, products)


def sitemap_urls(client, config):
    pattern = re.compile(config.get('url_pattern', r'/products/'))
    queue = list(config['sitemaps'])
    seen, urls = set(), []
    while queue:
        sitemap = queue.pop(0)
        if sitemap in seen:
            continue
        seen.add(sitemap)
        body = client.get(sitemap)
        locs = [html.unescape(u) for u in re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', body)]
        if '<sitemapindex' in body:
            child_pattern = re.compile(config.get('sitemap_pattern', r'product'), re.I)
            queue += [u for u in locs if child_pattern.search(u)]
            continue
        urls += [u for u in locs if pattern.search(u) and not re.search(r'\.(jpe?g|png|webp)$', u)]
    deduped = list(dict.fromkeys(urls))
    client.log(f'{config["name"]}: {len(deduped)} product URLs from {len(seen)} sitemap file(s)')
    return deduped


def strategy_shopify_handles(config, client, limit=None):
    origin = config['origin']
    currency = shopify_currency(client, origin, config)
    products = {}
    urls = sitemap_urls(client, config)
    for index, url in enumerate(urls[:limit] if limit else urls, 1):
        handle = urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1]
        raw = client.get(f'{origin}/products/{handle}.js', as_json=True, allow_404=True)
        if raw is None:
            continue
        products[str(raw['id'])] = normalize_shopify_js(raw, origin)
        if index % 25 == 0:
            client.log(f'{config["name"]}: {index}/{len(urls)} products read')
    return snapshot(config, currency, products)


def jsonld_products(markup):
    found = []
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', markup, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get('@graph', [data])
        found += [i for i in items if isinstance(i, dict) and i.get('@type') in ('Product', 'ProductGroup')]
    return found


def offers_of(item):
    offers = item.get('offers') or []
    if isinstance(offers, dict):
        offers = offers.get('offers', [offers]) if offers.get('@type') == 'AggregateOffer' else [offers]
    return offers


def parse_jsonld_page(markup, url):
    items = jsonld_products(markup)
    if not items:
        return None
    root = items[0]
    variants = {}
    members = root.get('hasVariant') or [root]
    for member in members:
        for offer in offers_of(member):
            sku = offer.get('sku') or member.get('sku') or root.get('sku')
            vid = sku or offer.get('url') or url
            label = member.get('size') or member.get('name') if member is not root else (sku or 'Default')
            available = 'InStock' in str(offer.get('availability', '')) or 'PreOrder' in str(offer.get('availability', ''))
            variants[str(vid)] = variant_record(vid, label, minor_units(offer.get('price')), available, sku)
    if not variants:
        return None
    images = root.get('image') or []
    images = [images] if isinstance(images, str) else [i if isinstance(i, str) else i.get('url') for i in images]
    pid = root.get('productGroupID') or root.get('sku') or root.get('@id') or url
    return product_record(pid, root.get('name'), url, variants, description=root.get('description'),
                          vendor=(root.get('brand') or {}).get('name') if isinstance(root.get('brand'), dict) else root.get('brand'),
                          images=[i for i in images if i])


def parse_meta_page(markup, url):
    """Fallback for pages without JSON-LD (e.g. Next.js RSC payloads)."""
    soup = BeautifulSoup(markup, 'html.parser')
    title = soup.select_one('meta[property="og:title"]')
    title = title['content'] if title else (soup.title.get_text(strip=True) if soup.title else None)
    price = re.search(r'\\?"(?:discounted_price|special_price|final_price|price)\\?"\s*:\s*\\?"?([\d,]+(?:\.\d+)?)', markup)
    original = re.search(r'\\?"original_price\\?"\s*:\s*\\?"?([\d,]+(?:\.\d+)?)', markup)
    sku = re.search(r'\\?"sku\\?"\s*:\s*\\?"([^"\\]+)', markup)
    stock = re.search(r'\\?"(?:stock_status|is_in_stock|availability)\\?"\s*:\s*\\?"?([A-Za-z_]+|true|false|1|0)', markup)
    sold_out = re.search(r'\\?"sold_out\\?"\s*:\s*(true|false)', markup)
    if not title or not price:
        return None
    available = not stock or stock[1].lower() in ('in_stock', 'instock', 'true', '1')
    if sold_out:
        available = sold_out[1] == 'false'
    compare_at = minor_units(original[1]) if original else None
    vid = sku[1] if sku else url
    variants = {vid: variant_record(vid, 'Default', minor_units(price[1]), available, sku[1] if sku else None,
                                    compare_at if compare_at != minor_units(price[1]) else None)}
    image = soup.select_one('meta[property="og:image"]')
    return product_record(vid, title, url, variants, images=[image['content']] if image else [])


def strategy_sitemap_jsonld(config, client, limit=None):
    products, failures = {}, 0
    urls = sitemap_urls(client, config)
    for index, url in enumerate(urls[:limit] if limit else urls, 1):
        try:
            markup = client.get(url, allow_404=True)
        except ValueError:
            markup = None
        product = None
        if markup:
            product = parse_jsonld_page(markup, url) or (parse_meta_page(markup, url) if config.get('meta_fallback') else None)
        if product is None:
            failures += 1
        else:
            products.setdefault(product['id'], product)
        if index % 25 == 0:
            client.log(f'{config["name"]}: {index}/{len(urls)} pages read, {len(products)} products, {failures} unparsed')
    checked = min(len(urls), limit or len(urls))
    if checked and failures > checked * 0.2:
        raise ValueError(f'{config["name"]}: {failures}/{checked} product pages unparsed; refusing partial scan')
    return snapshot(config, 'PKR', products)


def sfcc_tiles(markup, origin):
    soup = BeautifulSoup(markup, 'html.parser')
    tiles = []
    for node in soup.select('div.product[data-pid]'):
        holder = node if node.has_attr('data-gtmdata') else node.select_one('[data-gtmdata]')
        if holder is None:
            continue
        data = json.loads(html.unescape(holder['data-gtmdata']))
        link = node.select_one('a.plpRedirectPdp[href], a.link[href], .pdp-link a[href], a[href*=".html"]')
        url = urljoin(origin, link['href'].split('?')[0]) if link else origin
        strike = node.select_one('.strike-through .value[content], .strike-through [content], del .value[content]')
        text = node.get_text(' ', strip=True).lower()
        image = node.select_one('img.tile-image')
        image = (image.get('data-src') or image.get('src')) if image else None
        price = node.select_one('.sales .value[content]')
        if price and not data.get('price'):
            data['price'] = price['content']
        tiles.append({'pid': node['data-pid'], 'name': data.get('name'), 'price': minor_units(data.get('price')),
                      'compare_at': minor_units(strike['content']) if strike else None, 'url': url,
                      'category': data.get('category'),
                      'available': not re.search(r'sold out|out of stock', text),
                      'image': image})
    return tiles


def strategy_sfcc(config, client, limit=None, page_size=48, max_pages=60):
    origin = config['origin']
    products = {}
    for category in config['category_urls']:
        before = len(products)
        for page in range(max_pages):
            url = f'{category}{"&" if "?" in category else "?"}start={page * page_size}&sz={page_size}'
            tiles = sfcc_tiles(client.get(url), origin)
            fresh = 0
            for tile in tiles:
                if tile['pid'] in products:
                    continue
                fresh += 1
                variants = {tile['pid']: variant_record(tile['pid'], 'Default', tile['price'], tile['available'],
                                                        tile['pid'], tile['compare_at'])}
                products[tile['pid']] = product_record(tile['pid'], tile['name'], tile['url'], variants,
                                                       type=tile['category'],
                                                       images=[tile['image']] if tile['image'] else [])
            if len(tiles) < page_size or (not fresh and page > 0):
                break
            if limit and len(products) >= limit:
                break
        client.log(f'{config["name"]}: {category} -> +{len(products) - before} products ({len(products)} total)')
        if limit and len(products) >= limit:
            break
    return snapshot(config, 'PKR', products)


def turbo_stream(markup):
    """Decode the React Router turbo-stream payload embedded in Shopify Hydrogen pages."""
    chunks = re.findall(r'streamController\.enqueue\((".*?")\);', markup, re.S)
    if not chunks:
        return None
    flat = json.loads(''.join(json.loads(c) for c in chunks).split('\n', 1)[0])
    cache = {}

    def value(index):
        if not isinstance(index, int) or index < 0:
            return None
        if index in cache:
            return cache[index]
        raw = flat[index]
        if isinstance(raw, dict):
            out = cache[index] = {}
            for key, ref in raw.items():
                out[flat[int(key[1:])]] = value(ref)
            return out
        if isinstance(raw, list):
            if raw and isinstance(raw[0], str) and len(raw[0]) == 1:
                cache[index] = None
                return None
            out = cache[index] = []
            out.extend(value(ref) for ref in raw)
            return out
        cache[index] = raw
        return raw

    return value(0)


def walk(node, depth=0):
    if depth > 40:
        return
    yield node
    children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
    for child in children:
        yield from walk(child, depth + 1)


def is_product_node(node):
    return isinstance(node, dict) and isinstance(node.get('handle'), str) \
        and str(node.get('id', '')).startswith('gid://shopify/Product/')


def hydrogen_page(root):
    """Return (product nodes, next cursor, total) from a decoded collection page."""
    for node in walk(root):
        if isinstance(node, dict) and isinstance(node.get('nodes'), list) and isinstance(node.get('pageInfo'), dict):
            products = [n for n in node['nodes'] if is_product_node(n)]
            if products:
                info = node['pageInfo']
                return products, info.get('endCursor') if info.get('hasNextPage') else None, None
    for node in walk(root):
        if isinstance(node, dict) and isinstance(node.get('products'), list) and isinstance(node.get('pagination'), dict):
            products = [n for n in node['products'] if is_product_node(n)]
            page = node['pagination']
            more = page.get('page', 1) < page.get('pageCount', 1)
            return products, ('page', page['page'] + 1) if more else None, page.get('total')
    return [], None, None


def amount(value):
    if isinstance(value, dict):
        value = value.get('amount')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(round(value * 100))
    return minor_units(value)


def hydrogen_product(node, origin):
    """Product-level record from a listing node; available=None means 'listing cannot tell'."""
    first = ((node.get('variants') or {}).get('nodes') or [{}])[0] or {}
    if isinstance(node.get('available'), bool):
        available = node['available']
    elif isinstance(node.get('availableForSale'), bool):
        available = node['availableForSale']
    elif isinstance(first.get('availableForSale'), bool):
        # Listings expose only the first size: True proves availability, False needs confirmation.
        available = True if first['availableForSale'] else None
    else:
        available = None
    price = amount(node.get('price')) or amount(first.get('price')) \
        or amount(((node.get('priceRange') or {}).get('minVariantPrice')))
    compare = amount(node.get('compareAtPrice')) or amount(first.get('compareAtPrice')) \
        or amount(((node.get('compareAtPriceRange') or {}).get('maxVariantPrice')))
    if compare is not None and price is not None and compare <= price:
        compare = None
    image = node.get('featuredImage') or ((node.get('images') or {}).get('nodes') or [None])[0] \
        if isinstance(node.get('images'), dict) else (node.get('images') or [None])[0]
    image = image.get('url') if isinstance(image, dict) else image
    pid = node['id'].rsplit('/', 1)[-1]
    variants = {pid: variant_record(pid, 'Default', price, bool(available), None, compare)}
    record = product_record(pid, node['title'], f'{origin}/products/{node["handle"]}', variants,
                            images=[image] if image else [])
    return record, available is None


def confirm_from_page(client, record):
    """Product page JSON-LD is in stock if any offer is; used only when the listing could not tell."""
    markup = client.get(record['url'], allow_404=True)
    if markup is None:
        return False
    offers = [o for item in jsonld_products(markup) for o in offers_of(item)]
    return any('InStock' in str(o.get('availability', '')) or 'PreOrder' in str(o.get('availability', ''))
               for o in offers)


def product_from_page(client, url, origin):
    markup = client.get(url, allow_404=True)
    if markup is None:
        return None
    handle = urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1]
    root = turbo_stream(markup)
    node = next((n for n in walk(root) if is_product_node(n) and n['handle'] == handle), None) if root else None
    parsed = parse_jsonld_page(markup, url)
    if node is None or parsed is None:
        return None
    pid = node['id'].rsplit('/', 1)[-1]
    variant = next(iter(parsed['variants'].values()))
    available = any(v['available'] for v in parsed['variants'].values())
    variants = {pid: variant_record(pid, 'Default', variant['price'], available, None, None)}
    return product_record(pid, node.get('title') or parsed['title'], f'{origin}/products/{handle}', variants,
                          images=parsed['images'][:1])


def strategy_hydrogen_listing(config, client, limit=None, max_pages=1000):
    """Shopify Hydrogen: page through /collections/all, confirm unclear stock, then cover sitemap gaps."""
    origin = config['origin']
    base = origin + config.get('collection_path', '/collections/all')
    products, unclear, total, cursor = {}, [], None, None
    for page in range(1, max_pages + 1):
        if cursor is None:
            url = base
        elif cursor[0] == 'page':
            url = f'{base}?page={cursor[1]}'
        else:
            url = f'{base}?cursor={quote(cursor)}&direction=next'
        root = turbo_stream(client.get(url))
        nodes, next_cursor, page_total = hydrogen_page(root) if root else ([], None, None)
        total = page_total or total
        fresh = 0
        for node in nodes:
            record, needs_check = hydrogen_product(node, origin)
            if record['id'] in products:
                continue
            fresh += 1
            products[record['id']] = record
            if needs_check:
                unclear.append(record)
        if page % 20 == 0 or not next_cursor:
            client.log(f'{config["name"]}: listing page {page}: {len(products)} products')
        if not nodes and page == 1:
            raise ValueError(f'{config["name"]}: collection page has no product data; refusing to save state')
        if not next_cursor or not fresh or (limit and len(products) >= limit):
            break
        cursor = next_cursor
    if total and not limit and abs(len(products) - total) > max(2, total * 0.02):
        raise ValueError(f'{config["name"]}: listing completeness check failed: {len(products)} of {total}')
    client.log(f'{config["name"]}: confirming {len(unclear)} products whose first size is sold out')
    for record in unclear:
        available = confirm_from_page(client, record)
        for variant in record['variants'].values():
            variant['available'] = available
        record['available'] = available
    if config.get('sitemaps') and not limit:
        listed = {p['handle'] for p in products.values()}
        missing = [u for u in sitemap_urls(client, config)
                   if urlsplit(u).path.rstrip('/').rsplit('/', 1)[-1] not in listed]
        client.log(f'{config["name"]}: {len(missing)} sitemap products not in the listing; reading them individually')
        for url in missing:
            record = product_from_page(client, url, origin)
            if record:
                products.setdefault(record['id'], record)
    return snapshot(config, 'PKR', products)


def next_flight_payload(markup):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', markup, re.S)
    return ''.join(json.loads('"' + c + '"') for c in chunks)


def bareeze_listing(markup):
    payload = next_flight_payload(markup)
    start = payload.find('"count":')
    data_at = payload.find('"data":[', start)
    if start < 0 or data_at < 0:
        return 0, []
    count = int(re.match(r'"count":(\d+)', payload[start:])[1])
    data, _ = json.JSONDecoder().raw_decode(payload, data_at + 7)
    return count, data


def strategy_bareeze_listing(config, client, limit=None):
    """Next.js storefront: every top-level category, fetched via its cumulative 'load more' last page."""
    origin = config['origin']
    body = client.get(config['category_sitemap'])
    paths = re.findall(r'<loc>\s*https?://[^/]+/([^<\s]+)', body)
    skip = set(config.get('skip_categories', []))
    categories = sorted({p.split('/')[0] for p in paths} - skip)
    client.log(f'{config["name"]}: {len(categories)} top-level categories')
    products = {}
    for category in categories:
        url = f'{origin}/{category}'
        count, data = bareeze_listing(client.get(url, allow_404=True) or '')
        if count > len(data) and data:
            count, data = bareeze_listing(client.get(f'{url}?page={-(-count // len(data))}'))
        if count and len(data) < count:
            raise ValueError(f'{config["name"]}: {category} returned {len(data)} of {count} products')
        before = len(products)
        for item in data:
            pid = str(item['id'])
            if pid in products:
                continue
            prices = item.get('variant_detail') or {}
            price, original = minor_units(prices.get('discounted_price')), minor_units(prices.get('original_price'))
            variants = {pid: variant_record(pid, 'Default', price, not item.get('sold_out'), None,
                                            original if original and original != price else None)}
            products[pid] = product_record(pid, item['title'], f'{origin}/{item["handle"]}', variants,
                                           images=(item.get('images') or [])[:1])
        client.log(f'{config["name"]}: {category}: {count} listed, +{len(products) - before} new ({len(products)} total)')
        if limit and len(products) >= limit:
            break
    return snapshot(config, 'PKR', products)


STRATEGIES = {
    'shopify_json': strategy_shopify_json,
    'shopify_handles': strategy_shopify_handles,
    'sitemap_jsonld': strategy_sitemap_jsonld,
    'sfcc': strategy_sfcc,
    'hydrogen_listing': strategy_hydrogen_listing,
    'bareeze_listing': strategy_bareeze_listing,
}


def strategy_monitor_store(config, pause, old, log):
    """Khushposh/Outfitters: delegate to monitor.py's own scanner so behaviour and baselines are unchanged."""
    import monitor
    from playwright.sync_api import sync_playwright
    store = monitor.STORES[config['store']]
    with sync_playwright() as playwright:
        request = playwright.request.new_context(
            **monitor.request_options(), user_agent=f'{store.name}StockMonitor/1.0',
            extra_http_headers={'Cache-Control': 'no-cache'},
            storage_state={'cookies': [{'name': 'localization', 'value': 'PK',
                                        'domain': urlsplit(store.origin).hostname, 'path': '/', 'expires': -1,
                                        'httpOnly': False, 'secure': True, 'sameSite': 'Lax'}],
                           'origins': []})
        try:
            return monitor.scan(request, pause, store, old=old)
        finally:
            request.dispose()


def run(config, limit=None, pause=0.35, log=print, old=None):
    if config['strategy'] == 'unavailable':
        raise Unavailable(f'{config["name"]}: {config.get("reason", "no public catalog")}')
    if config['strategy'] == 'monitor_store':
        if limit:
            log(f'{config["name"]}: --limit not supported by monitor.py; scanning the full catalog')
        return strategy_monitor_store(config, pause, old, log)
    client = Client(config['origin'], pause=max(pause, config.get('min_pause', 0)), log=log,
                    fail_fast_429=limit is not None)
    result = STRATEGIES[config['strategy']](config, client, limit=limit)
    log(f'{config["name"]}: {client.requests} HTTP requests')
    return result
