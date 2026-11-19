"""Load scraper snapshots from the monitor-state branch into Postgres.

    python -m pipeline.ingest                       # every enabled brand, new commits only
    python -m pipeline.ingest --brand khaadi saya
    python -m pipeline.ingest --stats               # table sizes and row counts

The monitor-state branch stays the source of truth: every commit that touched
brands/<slug>/state.json is one scan. Each is loaded in its own transaction, compared with the
rows already in the database, and turned into history points and events. Re-running is a no-op
(scans are keyed by brand + commit), so the same code does the backfill and the daily run.

Needs DATABASE_URL. Only brands listed in pipeline/ingest_brands.json are loaded; optional
INGEST_BRANDS="slug slug" narrows a run further.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from pipeline import normalize, notify_run, notify_watches

ROOT = Path(__file__).resolve().parent.parent
SCRAPERS = ROOT / 'brands' / 'scrapers.json'
BRAND_CONFIG = Path(__file__).resolve().parent / 'ingest_brands.json'
BRAND_TYPES = Path(__file__).resolve().parent / 'brand_types.json'
LABEL_SOURCES = (Path(__file__).resolve().parent / 'normalize.py', BRAND_TYPES)
DEFAULT_REF = 'origin/monitor-state'
PRODUCT_LEVEL_STRATEGIES = {'sfcc', 'bareeze_listing', 'hydrogen_listing', 'sitemap_jsonld'}
NOTIFY_WINDOW = timedelta(hours=24)
MIN_OVERLAP = 0.5
# A brand that has never been loaded is not started once the database is this big. The free
# Supabase tier turns read-only above 500 MB, so stop well short of it. INGEST_MAX_DB_MB overrides.
DEFAULT_MAX_DB_MB = 420


class Rejected(Exception):
    """The snapshot is unsafe to load; the database keeps its last good data."""


def log(message):
    print(f'{time.strftime("%H:%M:%S")} {message}', flush=True)


# ---------------------------------------------------------------- git access

def git(*args, cwd=ROOT):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, check=True).stdout


def state_path(slug):
    return f'brands/{slug}/state.json'


class HistoryRewritten(Exception):
    """The last loaded commit is not in the branch history (the history was replaced)."""


def commits_after(slug, ref, cursor, cwd=ROOT):
    """Commits on ref that touched this brand's snapshot after the cursor, oldest first."""
    if cursor:
        try:
            git('merge-base', '--is-ancestor', cursor, ref, cwd=cwd)
        except subprocess.CalledProcessError:
            raise HistoryRewritten(f'cursor {cursor[:10]} is not on {ref}') from None
    span = f'{cursor}..{ref}' if cursor else ref
    out = git('log', '--reverse', '--format=%H', span, '--', state_path(slug), cwd=cwd)
    return out.decode().split()


def load_snapshot(slug, sha, cwd=ROOT):
    return json.loads(git('show', f'{sha}:{state_path(slug)}', cwd=cwd))


# ---------------------------------------------------------------- brands

def sync_brands(conn, configs):
    """Create or refresh brand rows from brands/scrapers.json. Operator-edited columns
    (is_visible, scan_tier, ingest_enabled, logo_url, affiliate_template) are left alone."""
    for slug, config in configs.items():
        granularity = 'product' if config['strategy'] in PRODUCT_LEVEL_STRATEGIES else 'variant'
        conn.execute(
            """insert into brands (slug, name, origin_url, strategy, granularity, is_visible)
               values (%s, %s, %s, %s, %s, %s)
               on conflict (slug) do update set name = excluded.name, origin_url = excluded.origin_url,
                 strategy = excluded.strategy, granularity = excluded.granularity
               where (brands.name, brands.origin_url, brands.strategy, brands.granularity)
                 is distinct from (excluded.name, excluded.origin_url, excluded.strategy, excluded.granularity)""",
            (slug, config['name'], config.get('origin') or config.get('website') or '', config['strategy'],
             granularity, config['strategy'] != 'unavailable'))


# ---------------------------------------------------------------- one snapshot

def validate(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get('schema_version') != 1:
        raise Rejected(f'schema_version is {snapshot.get("schema_version") if isinstance(snapshot, dict) else None}, expected 1')
    if snapshot.get('currency') != 'PKR':
        raise Rejected(f'currency is {snapshot.get("currency")}, expected PKR')
    if snapshot.get('price_unit') != 'minor_units':
        raise Rejected(f'price_unit is {snapshot.get("price_unit")}, expected minor_units')
    if not isinstance(snapshot.get('products'), dict) or not snapshot['products']:
        raise Rejected('snapshot has no products')
    try:
        checked_at = datetime.fromisoformat(snapshot['checked_at'])
    except (KeyError, TypeError, ValueError):
        raise Rejected('checked_at is missing or not an ISO timestamp') from None
    if checked_at.tzinfo is None:
        raise Rejected('checked_at has no timezone')
    return checked_at


def load_brand_types(path=BRAND_TYPES):
    """Per-brand label settings (pipeline/brand_types.json), validated so a typo fails loudly."""
    brands = json.loads(path.read_text(encoding='utf-8'))['brands'] if path.exists() else {}
    for slug, entry in brands.items():
        unknown = set(entry) - {'show_types', 'primary', 'types'}
        if unknown:
            raise ValueError(f'{path.name}: {slug} has unknown keys {sorted(unknown)}')
        for category in [entry.get('primary'), *(entry.get('types') or {}).values()]:
            if category is not None and category not in normalize.CATEGORIES:
                raise ValueError(f'{path.name}: {slug} uses unknown category {category!r}')
    return brands


def labels_version():
    """Changes whenever the labelling code or the brand settings change."""
    digest = hashlib.sha256()
    for path in LABEL_SOURCES:
        digest.update(path.read_bytes() if path.exists() else b'')
    return digest.hexdigest()[:16]


def apply_brand_settings(conn, brand_types):
    for slug, show in conn.execute('select slug, show_types from brands').fetchall():
        wanted = (brand_types.get(slug) or {}).get('show_types', True)
        if wanted != show:
            conn.execute('update brands set show_types = %s where slug = %s', (wanted, slug))


def relabel(conn, brand_types, brand_ids=None):
    """Recompute category and gender of stored products from their stored fields, and write only
    the ones that changed. Returns the number of products updated."""
    brands = {row[0]: row[1] for row in conn.execute('select id, slug from brands').fetchall()}
    query = 'select id, brand_id, title, raw_type, tags, handle, vendor, category, gender from products'
    params = ()
    if brand_ids is not None:
        query += ' where brand_id = any(%s)'
        params = (list(brand_ids),)
    changed = []
    for pid, brand_id, title, raw_type, tags, handle, vendor, category, gender in conn.execute(query, params):
        item = {'title': title, 'type': raw_type, 'tags': tags, 'handle': handle, 'vendor': vendor}
        new = (normalize.category_of(item, brand_types.get(brands[brand_id])), normalize.gender_of(item))
        if new != (category, gender):
            changed.append((pid, *new))
    if changed:
        with conn.transaction():
            cur = conn.cursor()
            cur.execute('create temp table relabel (id bigint primary key, category text, gender text) on commit drop')
            with cur.copy('copy relabel from stdin') as copy:
                for row in changed:
                    copy.write_row(row)
            cur.execute("""update products p set category = r.category, gender = r.gender,
                             search = product_search_vector(p.title, b.name, p.raw_type, p.tags, r.category)
                           from relabel r, brands b where p.id = r.id and b.id = p.brand_id""")
    return len(changed)


def relabel_if_rules_changed(conn, brand_types):
    version = labels_version()
    stored = conn.execute("select value from pipeline_meta where key = 'labels_version'").fetchone()
    if stored and stored[0] == version:
        return None
    count = relabel(conn, brand_types)
    conn.execute("""insert into pipeline_meta (key, value) values ('labels_version', %s)
                    on conflict (key) do update set value = excluded.value, updated_at = now()""", (version,))
    return count


def product_rows(snapshot, rules=None):
    for external_id, product in snapshot['products'].items():
        tags = [normalize.clean_text(tag) for tag in product.get('tags') or [] if tag is not None]
        options = product.get('options')
        yield (
            str(external_id),
            normalize.clean_text(product.get('title')) or '',
            normalize.clean_text(product.get('handle')),
            normalize.clean_text(product.get('url')) or '',
            normalize.clean_text(product.get('vendor')),
            normalize.clean_text(product.get('type')),
            normalize.clean_description(product.get('description')),
            tags,
            normalize.clean_images(product.get('images')),
            None,  # product-level option lists are not stored (2026-11-19, to save space)
            normalize.category_of(product, rules),
            normalize.gender_of(product),
        )


def variant_rows(snapshot):
    for product_id, product in snapshot['products'].items():
        for external_id, variant in (product.get('variants') or {}).items():
            price = variant.get('price')
            compare_at = variant.get('compare_at_price')
            if isinstance(price, bool) or not isinstance(price, int) or price < 0:
                raise Rejected(f'variant {external_id} of product {product_id} has price {price!r}')
            if compare_at is not None and (isinstance(compare_at, bool) or not isinstance(compare_at, int)):
                raise Rejected(f'variant {external_id} of product {product_id} has compare_at_price {compare_at!r}')
            options = [normalize.clean_text(value) for value in variant.get('options') or [] if value is not None]
            yield (
                str(product_id),
                str(external_id),
                normalize.clean_text(variant.get('title')),
                options,
                normalize.variant_size(product.get('options'), options),
                normalize.clean_text(variant.get('sku')),
                bool(variant.get('available')),
                price,
                compare_at,
            )


STAGING = """
create temp table stg_p (
  external_id text primary key, title text not null, handle text, url text not null, vendor text,
  raw_type text, description text, tags text[] not null, images text[] not null, options jsonb,
  category text, gender text
) on commit drop;
create temp table stg_v (
  product_ext text not null, external_id text not null, title text, options text[], size_norm text,
  sku text, available boolean not null, price bigint not null, compare_at_price bigint,
  primary key (product_ext, external_id)
) on commit drop;
create temp table touched (product_id bigint primary key) on commit drop;
create temp table new_products (product_id bigint primary key) on commit drop;
"""

# Skipped on a brand's first scan: nothing can be missing yet, and the planner has no statistics
# for the rows that scan just inserted.
REMOVED_VARIANTS = """with gone as (
     update variants v set removed_at = %(at)s
     from products p
     where v.product_id = p.id and p.brand_id = %(brand)s and p.removed_at is null and v.removed_at is null
       and not exists (select 1 from stg_vm m where m.product_id = v.product_id and m.external_id = v.external_id)
     returning v.id, v.product_id, v.available, v.first_seen_at),
   baseline as (
     insert into stock_points (variant_id, observed_at, available)
     select g.id, g.first_seen_at, true from gone g
     where g.available and not exists (select 1 from stock_points sp where sp.variant_id = g.id)
     on conflict do nothing),
   point as (
     insert into stock_points (variant_id, observed_at, available)
     select g.id, %(at)s, false from gone g where g.available
     on conflict do nothing)
   insert into touched select distinct product_id from gone on conflict do nothing"""

# Each statement takes the same parameter dict. Order matters.
MERGE = (
    # Products that were marked removed and are listed again.
    """with back as (
         update products p set removed_at = null
         from stg_p s
         where p.brand_id = %(brand)s and p.external_id = s.external_id and p.removed_at is not null
         returning p.id)
       insert into touched select id from back on conflict do nothing""",

    # Descriptive fields that changed. No event: these are not what users follow.
    """update products p set title = s.title, handle = s.handle, url = s.url, vendor = s.vendor,
         raw_type = s.raw_type, description = s.description, tags = s.tags, images = s.images,
         options = s.options, category = s.category, gender = s.gender,
         search = product_search_vector(s.title, %(brand_name)s, s.raw_type, s.tags, s.category)
       from stg_p s
       where p.brand_id = %(brand)s and p.external_id = s.external_id
         and (p.title, p.handle, p.url, p.vendor, p.raw_type, p.description, p.tags, p.images, p.options,
              p.category, p.gender)
             is distinct from
             (s.title, s.handle, s.url, s.vendor, s.raw_type, s.description, s.tags, s.images, s.options,
              s.category, s.gender)""",

    # New products are inserted with their product-level numbers already filled in, so the
    # later recompute step does not rewrite every freshly inserted row.
    """with agg as (
         select v.product_ext,
                bool_or(v.available) as available, min(v.price) as price_min, max(v.price) as price_max,
                max(v.compare_at_price) filter (where v.compare_at_price > v.price) as compare_at_max,
                coalesce(max(round(100.0 * (v.compare_at_price - v.price) / v.compare_at_price))
                         filter (where v.compare_at_price > v.price), 0)::smallint as discount_pct
         from stg_v v group by v.product_ext),
       ins as (
         insert into products (brand_id, external_id, title, handle, url, vendor, raw_type, description, tags,
                               images, options, category, gender, first_seen_at, search,
                               available, price_min, price_max, compare_at_max, discount_pct)
         select %(brand)s, s.external_id, s.title, s.handle, s.url, s.vendor, s.raw_type, s.description, s.tags,
                s.images, s.options, s.category, s.gender, %(at)s,
                product_search_vector(s.title, %(brand_name)s, s.raw_type, s.tags, s.category),
                coalesce(a.available, false), a.price_min, a.price_max, a.compare_at_max, coalesce(a.discount_pct, 0)
         from stg_p s
         left join agg a on a.product_ext = s.external_id
         where not exists (select 1 from products p where p.brand_id = %(brand)s and p.external_id = s.external_id)
         returning id)
       insert into new_products select id from ins""",

    'insert into touched select product_id from new_products on conflict do nothing',

    """insert into product_events (brand_id, product_id, kind, observed_at, scan_id, notifiable)
       select %(brand)s, product_id, 'new_product', %(at)s, %(scan)s, %(notifiable)s
       from new_products where not %(first)s""",

    # Products no longer listed.
    """with gone as (
         update products p set removed_at = %(at)s
         where p.brand_id = %(brand)s and p.removed_at is null
           and not exists (select 1 from stg_p s where s.external_id = p.external_id)
         returning p.id)
       insert into product_events (brand_id, product_id, kind, observed_at, scan_id, notifiable)
       select %(brand)s, id, 'removed', %(at)s, %(scan)s, false from gone""",

    # Pair every staged variant with its product and, when it exists, its current row.
    """create temp table stg_vm on commit drop as
       select p.id as product_id, v.id as variant_id, s.external_id, s.title, s.options, s.size_norm, s.sku,
              s.available, s.price, s.compare_at_price,
              v.price as old_price, v.compare_at_price as old_compare,
              (v.available and v.removed_at is null) as old_available,
              v.first_seen_at
       from stg_v s
       join products p on p.brand_id = %(brand)s and p.external_id = s.product_ext
       left join variants v on v.product_id = p.id and v.external_id = s.external_id""",
    'create index on stg_vm (product_id, external_id)',
    'analyze stg_vm',

    # Price history: the first change also records the price the variant had until now.
    """insert into price_points (variant_id, observed_at, price, compare_at_price)
       select m.variant_id, m.first_seen_at, m.old_price, m.old_compare
       from stg_vm m
       where m.variant_id is not null
         and (m.old_price, m.old_compare) is distinct from (m.price, m.compare_at_price)
         and not exists (select 1 from price_points pp where pp.variant_id = m.variant_id)
       on conflict do nothing""",
    """insert into price_points (variant_id, observed_at, price, compare_at_price)
       select m.variant_id, %(at)s, m.price, m.compare_at_price
       from stg_vm m
       where m.variant_id is not null
         and (m.old_price, m.old_compare) is distinct from (m.price, m.compare_at_price)
       on conflict do nothing""",

    # Stock history, same rule.
    """insert into stock_points (variant_id, observed_at, available)
       select m.variant_id, m.first_seen_at, m.old_available
       from stg_vm m
       where m.variant_id is not null and m.old_available <> m.available
         and not exists (select 1 from stock_points sp where sp.variant_id = m.variant_id)
       on conflict do nothing""",
    """insert into stock_points (variant_id, observed_at, available)
       select m.variant_id, %(at)s, m.available
       from stg_vm m
       where m.variant_id is not null and m.old_available <> m.available
       on conflict do nothing""",

    # A size coming back is the one variant-level stock event (it is what size watches wait for).
    """insert into product_events (brand_id, product_id, variant_id, kind, observed_at, scan_id, notifiable)
       select %(brand)s, m.product_id, m.variant_id, 'back_in_stock', %(at)s, %(scan)s, %(notifiable)s
       from stg_vm m
       where %(by_variant)s and m.variant_id is not null and m.available and not m.old_available""",

    """with upd as (
         update variants v set title = m.title, options = m.options, size_norm = m.size_norm, sku = m.sku,
           available = m.available, price = m.price, compare_at_price = m.compare_at_price, removed_at = null
         from stg_vm m
         where v.id = m.variant_id
           and (v.title, v.options, v.size_norm, v.sku, v.available, v.price, v.compare_at_price, v.removed_at)
               is distinct from
               (m.title, m.options, m.size_norm, m.sku, m.available, m.price, m.compare_at_price, null::timestamptz)
         returning v.product_id)
       insert into touched select distinct product_id from upd on conflict do nothing""",

    """with ins as (
         insert into variants (product_id, external_id, title, options, size_norm, sku, available, price,
                               compare_at_price, first_seen_at)
         select m.product_id, m.external_id, m.title, m.options, m.size_norm, m.sku, m.available, m.price,
                m.compare_at_price, %(at)s
         from stg_vm m where m.variant_id is null
         returning id, product_id),
       ev as (
         insert into product_events (brand_id, product_id, variant_id, kind, observed_at, scan_id, notifiable)
         select %(brand)s, i.product_id, i.id, 'new_variant', %(at)s, %(scan)s, %(notifiable)s
         from ins i
         where %(by_variant)s and not %(first)s
           and not exists (select 1 from new_products n where n.product_id = i.product_id))
       insert into touched select distinct product_id from ins on conflict do nothing""",

    # Variants that disappeared from a product that is still listed.
    REMOVED_VARIANTS,

    # Product-level numbers and the events feeds and product watches use.
    """with agg as (
         select t.product_id,
                coalesce(bool_or(v.available), false) as available,
                min(v.price) as price_min,
                max(v.price) as price_max,
                max(v.compare_at_price) filter (where v.compare_at_price > v.price) as compare_at_max,
                coalesce(max(round(100.0 * (v.compare_at_price - v.price) / v.compare_at_price))
                         filter (where v.compare_at_price > v.price), 0)::smallint as discount_pct
         from touched t
         left join variants v on v.product_id = t.product_id and v.removed_at is null
         group by t.product_id),
       old as (
         select p.id, p.available, p.price_min, p.discount_pct
         from products p join touched t on t.product_id = p.id),
       upd as (
         update products p set available = a.available, price_min = a.price_min, price_max = a.price_max,
           compare_at_max = a.compare_at_max, discount_pct = a.discount_pct,
           last_price_change_at = case when p.price_min is not null and a.price_min is distinct from p.price_min
                                       then %(at)s else p.last_price_change_at end,
           last_restock_at = case when p.price_min is not null and a.available and not p.available
                                  then %(at)s else p.last_restock_at end
         from agg a
         where p.id = a.product_id
           and (p.available, p.price_min, p.price_max, p.compare_at_max, p.discount_pct)
               is distinct from (a.available, a.price_min, a.price_max, a.compare_at_max, a.discount_pct))
       insert into product_events (brand_id, product_id, kind, old_value, new_value, observed_at, scan_id, notifiable)
       select %(brand)s, o.id, e.kind,
              jsonb_build_object('price', o.price_min, 'available', o.available, 'discount_pct', o.discount_pct),
              jsonb_build_object('price', a.price_min, 'available', a.available, 'discount_pct', a.discount_pct),
              %(at)s, %(scan)s, %(notifiable)s
       from old o
       join agg a on a.product_id = o.id
       cross join lateral (values
         ('back_in_stock', a.available and not o.available),
         ('out_of_stock', o.available and not a.available),
         ('price_drop', a.price_min < o.price_min),
         ('price_rise', a.price_min > o.price_min),
         ('sale_started', a.discount_pct > 0 and o.discount_pct = 0),
         ('sale_ended', a.discount_pct = 0 and o.discount_pct > 0)) as e(kind, hit)
       where e.hit and not %(first)s
         and not exists (select 1 from new_products n where n.product_id = o.id)""",

    """update scans set
         product_count = (select count(*) from stg_p),
         change_count = (select count(*) from product_events where scan_id = %(scan)s)
       where id = %(scan)s""",
    """update brands set product_count = (select count(*) from stg_p), last_scan_at = %(at)s, last_success_at = %(at)s
       where id = %(brand)s""",
    """insert into ingest_cursor (brand_id, last_commit_sha) values (%(brand)s, %(sha)s)
       on conflict (brand_id) do update set last_commit_sha = excluded.last_commit_sha, updated_at = now()""",
)


def ingest_snapshot(conn, brand, sha, snapshot, *, now=None, force=False, brand_types=None):
    """Load one snapshot. Returns 'ok', 'skipped' (already loaded) or raises Rejected.

    brand is a row with id, name and granularity. The caller owns the connection; this function
    runs in one transaction and leaves nothing behind when it fails.
    """
    now = now or datetime.now(timezone.utc)
    checked_at = validate(snapshot)
    products = list(product_rows(snapshot, (brand_types or {}).get(brand.get('slug'))))
    variants = list(variant_rows(snapshot))
    with conn.transaction():
        cur = conn.cursor()
        existing = cur.execute('select status from scans where brand_id = %s and commit_sha = %s',
                               (brand['id'], sha)).fetchone()
        if existing and existing[0] == 'ok':
            return 'skipped'
        if existing:
            cur.execute('delete from scans where brand_id = %s and commit_sha = %s', (brand['id'], sha))
        cur.execute(STAGING)
        with cur.copy('copy stg_p from stdin') as copy:
            for row in products:
                copy.write_row(row)
        with cur.copy('copy stg_v from stdin') as copy:
            for row in variants:
                copy.write_row(row)
        cur.execute('analyze stg_p')
        cur.execute('analyze stg_v')
        live, overlap = cur.execute(
            """select count(*), count(s.external_id) from products p
               left join stg_p s on s.external_id = p.external_id
               where p.brand_id = %s and p.removed_at is null""", (brand['id'],)).fetchone()
        if live and overlap < MIN_OVERLAP * live and not force:
            raise Rejected(f'only {overlap} of {live} live products are in this snapshot')
        first = not cur.execute('select exists (select 1 from products where brand_id = %s)',
                                (brand['id'],)).fetchone()[0]
        scan = cur.execute(
            "insert into scans (brand_id, commit_sha, checked_at, status) values (%s, %s, %s, 'ok') returning id",
            (brand['id'], sha, checked_at)).fetchone()[0]
        params = {'brand': brand['id'], 'brand_name': brand['name'], 'scan': scan, 'sha': sha, 'at': checked_at,
                  'first': first, 'notifiable': now - checked_at <= NOTIFY_WINDOW,
                  'by_variant': brand['granularity'] == 'variant'}
        for statement in MERGE:
            if first and statement is REMOVED_VARIANTS:
                continue
            cur.execute(statement, params)
        if first:
            cur.execute('analyze products')
            cur.execute('analyze variants')
    return 'ok'


def record_rejection(conn, brand, sha, snapshot, reason):
    """Remember a rejected snapshot and move past it: a later good scan repairs the brand,
    while re-reading the same bad commit every day never would."""
    checked_at = None
    try:
        checked_at = datetime.fromisoformat(snapshot.get('checked_at'))
    except (AttributeError, TypeError, ValueError):
        pass
    with conn.transaction():
        conn.execute(
            """insert into scans (brand_id, commit_sha, checked_at, status, error) values (%s, %s, %s, 'rejected', %s)
               on conflict (brand_id, commit_sha) do update set error = excluded.error, ingested_at = now()""",
            (brand['id'], sha, checked_at, reason))
        conn.execute('update brands set last_scan_at = coalesce(%s, last_scan_at) where id = %s',
                     (checked_at, brand['id']))
        conn.execute(
            """insert into ingest_cursor (brand_id, last_commit_sha) values (%s, %s)
               on conflict (brand_id) do update set last_commit_sha = excluded.last_commit_sha, updated_at = now()""",
            (brand['id'], sha))


# ---------------------------------------------------------------- driver

def ingest_brand(conn, brand, ref, *, force=False, max_commits=None, cwd=ROOT, now=None, brand_types=None):
    cursor = conn.execute('select last_commit_sha from ingest_cursor where brand_id = %s', (brand['id'],)).fetchone()
    try:
        commits = commits_after(brand['slug'], ref, cursor[0] if cursor else None, cwd=cwd)
    except HistoryRewritten as exc:
        # The snapshot branch was replaced (on 2026-11-19 the repository moved with its history
        # squashed). Each snapshot is compared with the database, not with git, so loading only the
        # newest one is correct; changes between the old and new history are seen as one step.
        commits = commits_after(brand['slug'], ref, None, cwd=cwd)[-1:]
        log(f'  {brand["slug"]}: {exc}; history was replaced, loading the newest snapshot only')
        if os.environ.get('GITHUB_ACTIONS') and commits:
            print(f'::warning::{brand["slug"]}: snapshot history was replaced; loaded the newest snapshot only')
    if max_commits:
        commits = commits[:max_commits]
    counts = {'ok': 0, 'skipped': 0, 'rejected': 0}
    for sha in commits:
        snapshot = load_snapshot(brand['slug'], sha, cwd=cwd)
        try:
            counts[ingest_snapshot(conn, brand, sha, snapshot, now=now, force=force,
                                   brand_types=brand_types)] += 1
        except Rejected as exc:
            counts['rejected'] += 1
            record_rejection(conn, brand, sha, snapshot, str(exc))
            log(f'  {brand["slug"]} {sha[:10]} REJECTED: {exc}')
    return counts


def included_slugs(path=BRAND_CONFIG):
    """The owner's brand selection, in priority order. Nothing is loaded for a brand that is not listed."""
    return list(dict.fromkeys(json.loads(path.read_text(encoding='utf-8'))['include']))


def enabled_brands(conn, only, included):
    rows = conn.execute('select id, slug, name, granularity from brands where ingest_enabled').fetchall()
    order = {slug: index for index, slug in enumerate(included)}
    brands = [dict(zip(('id', 'slug', 'name', 'granularity'), row)) for row in rows if row[1] in order]
    brands.sort(key=lambda brand: order[brand['slug']])
    if only:
        unknown = set(only) - {brand['slug'] for brand in brands}
        if unknown:
            raise SystemExit(f'not selected in {BRAND_CONFIG.name}, unknown or disabled: {" ".join(sorted(unknown))}')
        brands = [brand for brand in brands if brand['slug'] in only]
    return brands


def database_mb(conn):
    return conn.execute('select pg_database_size(current_database())').fetchone()[0] / 1048576


def has_room_for_new_brand(conn, brand, max_mb):
    """False when this brand has never been loaded and the database is already at its budget.
    Brands that are already loaded always keep updating."""
    loaded = conn.execute('select 1 from ingest_cursor where brand_id = %s', (brand['id'],)).fetchone()
    return bool(loaded) or database_mb(conn) < max_mb


def drop_brand(conn, slug):
    """Delete everything loaded for one brand (products, variants, history, events, scans, cursor)
    so its space can be reused. The brand row stays. Watches on its products are deleted with them."""
    row = conn.execute('select id from brands where slug = %s', (slug,)).fetchone()
    if not row:
        raise SystemExit(f'unknown brand: {slug}')
    with conn.transaction():
        removed = conn.execute('delete from products where brand_id = %s', (row[0],)).rowcount
        conn.execute('delete from scans where brand_id = %s', (row[0],))
        conn.execute('delete from ingest_cursor where brand_id = %s', (row[0],))
        conn.execute('update brands set product_count = 0, last_scan_at = null, last_success_at = null where id = %s',
                     (row[0],))
    return removed


def print_stats(conn):
    rows = conn.execute(
        """select c.relname, pg_total_relation_size(c.oid), c.reltuples::bigint
           from pg_class c join pg_namespace n on n.oid = c.relnamespace
           where n.nspname = 'public' and c.relkind = 'r' order by 2 desc""").fetchall()
    for name, size, estimate in rows:
        print(f'{name:<18} {size / 1048576:>9.1f} MB  ~{estimate:,} rows')
    total = conn.execute('select pg_database_size(current_database())').fetchone()[0]
    print(f'{"database":<18} {total / 1048576:>9.1f} MB')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--brand', nargs='*', default=[], help='Only these brand slugs')
    parser.add_argument('--ref', default=DEFAULT_REF, help=f'Branch holding the snapshots (default {DEFAULT_REF})')
    parser.add_argument('--max-commits', type=int, help='Load at most N commits per brand in this run')
    parser.add_argument('--force', action='store_true',
                        help='Accept snapshots that share under half of the live products (re-keyed or purged catalog)')
    parser.add_argument('--stats', action='store_true', help='Print table sizes and exit')
    parser.add_argument('--drop', metavar='SLUG', nargs='+',
                        help='Delete all loaded data of these brands and exit (remove them from ingest_brands.json too)')
    args = parser.parse_args()
    url = os.environ.get('DATABASE_URL')
    if not url:
        sys.exit('DATABASE_URL is not set')
    only = args.brand or os.environ.get('INGEST_BRANDS', '').split()
    max_mb = float(os.environ.get('INGEST_MAX_DB_MB') or DEFAULT_MAX_DB_MB)
    failed = rejected = 0
    no_room = []
    with psycopg.connect(url, autocommit=True) as conn:
        if args.stats:
            print_stats(conn)
            return 0
        if args.drop:
            for slug in args.drop:
                log(f'dropped {slug}: {drop_brand(conn, slug)} products')
            conn.execute('vacuum')  # lets later loads reuse the space; the file shrinks only with VACUUM FULL
            return 0
        run_started = conn.execute('select now()').fetchone()[0]
        sync_brands(conn, json.loads(SCRAPERS.read_text(encoding='utf-8')))
        brand_types = load_brand_types()
        apply_brand_settings(conn, brand_types)
        relabelled = relabel_if_rules_changed(conn, brand_types)
        if relabelled is not None:
            log(f'labelling rules changed: re-labelled {relabelled} products')
        brands = enabled_brands(conn, only, included_slugs())
        if not brands:
            log(f'no brands selected in {BRAND_CONFIG.name}; nothing to do')
        for index, brand in enumerate(brands, 1):
            started = time.time()
            if not has_room_for_new_brand(conn, brand, max_mb):
                no_room.append(brand['slug'])
                continue
            try:
                counts = ingest_brand(conn, brand, args.ref, force=args.force, max_commits=args.max_commits,
                                      brand_types=brand_types)
            except Exception as exc:  # one brand must not stop the others
                failed += 1
                log(f'[{index:02d}/{len(brands)}] {brand["slug"]} FAILED {type(exc).__name__}: {str(exc)[:300]}')
                continue
            rejected += counts['rejected']
            if any(counts.values()):
                log(f'[{index:02d}/{len(brands)}] {brand["slug"]} loaded {counts["ok"]}, '
                    f'rejected {counts["rejected"]} [{time.time() - started:.1f}s]')
        if os.environ.get('PUSH_NOTIFY', 'on').strip().lower() not in ('off', '0', 'false', 'no'):
            try:
                notify_watches.notify_watchers(conn, run_started, log=log)
            except Exception as exc:  # a push problem must never fail the data load
                log(f'watch alerts FAILED {type(exc).__name__}: {str(exc)[:300]}')
                if os.environ.get('GITHUB_ACTIONS'):
                    print(f'::warning::Watch alerts failed: {str(exc)[:200]}')
            try:
                notify_run.notify_after_run(conn, run_started, log=log)
            except Exception as exc:  # a push problem must never fail the data load
                log(f'push FAILED {type(exc).__name__}: {str(exc)[:300]}')
                if os.environ.get('GITHUB_ACTIONS'):
                    print(f'::warning::Push notification failed: {str(exc)[:200]}')
        if no_room:
            log(f'NOT LOADED, database is at {database_mb(conn):.0f} MB of the {max_mb:.0f} MB budget: {" ".join(no_room)}')
    log(f'done: {len(brands)} brands, {failed} failed, {rejected} snapshot(s) rejected, {len(no_room)} not loaded for space')
    # A rejected snapshot is recorded and skipped by design, and a brand left out for space is a
    # choice the owner has to make: both are warnings. Only a brand that could not be processed fails the run.
    if os.environ.get('GITHUB_ACTIONS'):
        if rejected:
            print(f'::warning::{rejected} snapshot(s) rejected and skipped; see the REJECTED lines above')
        if no_room:
            print(f'::warning::Not loaded, database is at its size budget: {" ".join(no_room)}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
