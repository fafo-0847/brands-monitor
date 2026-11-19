"""Keep the database small (the free Supabase plan stops writes above 500 MB).

    python -m pipeline.maintain              # trim rows, delete old data, vacuum (every ingest run)
    python -m pipeline.maintain --compact    # also rebuild indexes and tables that fit (on request)
    python -m pipeline.maintain --stats      # sizes only

Everything works in small batches outside a long transaction, with VACUUM in between, so the space
freed by one batch is reused by the next and the database does not grow while trimming.

Trimming (the same rules ingest applies to new data, so ingest never rewrites these rows again):
at most 3 images per product without Shopify's ?v= parameter, descriptions cut to 500 characters,
no product-level option lists.

Retention: product_events older than EVENTS_KEEP_DAYS (90) and products that left the store more
than REMOVED_KEEP_DAYS (60) ago, with their variants and history. Price history is kept.

Compacting: plain VACUUM lets Postgres reuse freed space but does not shrink the files. Rebuilding
(REINDEX, VACUUM FULL) shrinks them but needs room for a second copy while it runs, so each index and
table is rebuilt only when the database plus that copy stays under COMPACT_MAX_DB_MB (495).
"""
import argparse
import os
import sys
import time

import psycopg

from pipeline import normalize

BATCH = 5000


def log(message):
    print(f'{time.strftime("%H:%M:%S")} {message}', flush=True)


def database_mb(conn):
    return conn.execute('select pg_database_size(current_database())').fetchone()[0] / 1048576


def vacuum(conn, table):
    conn.execute(f'vacuum (analyze) {table}')


def trim_products(conn, batch=BATCH, log=log):
    """Apply the image, description and option limits to stored products. Returns rows changed."""
    low, high = conn.execute('select min(id), max(id) from products').fetchone()
    if low is None:
        return 0
    changed = since_vacuum = 0
    for start in range(low, high + 1, batch):
        count = conn.execute(f"""
            update products p set
              images = coalesce((select array_agg(private.clean_image_url(u) order by o)
                                 from unnest(p.images[1:{normalize.IMAGE_LIMIT}]) with ordinality as t(u, o)), '{{}}'),
              description = left(p.description, {normalize.DESCRIPTION_LIMIT}),
              options = null
            where p.id between %s and %s
              and (p.options is not null
                   or length(p.description) > {normalize.DESCRIPTION_LIMIT}
                   or cardinality(p.images) > {normalize.IMAGE_LIMIT}
                   or exists (select 1 from unnest(p.images) as u where u ~ '[?&]v=[0-9]'))""",
                             (start, start + batch - 1)).rowcount
        changed += count
        since_vacuum += count
        if since_vacuum >= 4 * batch:
            vacuum(conn, 'products')
            since_vacuum = 0
    if changed:
        vacuum(conn, 'products')
        log(f'trimmed {changed:,} products')
    return changed


def delete_in_batches(conn, query, params, batch=10000):
    """Run a `delete ... where id in (select id ... limit %s)` query until nothing is left."""
    total = 0
    while True:
        count = conn.execute(query, (*params, batch)).rowcount
        total += count
        if count < batch:
            return total


def apply_retention(conn, events_days=90, removed_days=60, log=log):
    events = delete_in_batches(conn, """
        delete from product_events where id in (
          select id from product_events where observed_at < now() - make_interval(days => %s) limit %s)""",
                               (events_days,))
    removed = delete_in_batches(conn, """
        delete from products where id in (
          select id from products where removed_at < now() - make_interval(days => %s) limit %s)""",
                                (removed_days,), batch=2000)
    if events:
        vacuum(conn, 'product_events')
    if removed:
        for table in ('products', 'variants', 'price_points', 'stock_points', 'product_events'):
            vacuum(conn, table)
    if events or removed:
        log(f'retention: deleted {events:,} changes older than {events_days} days and '
            f'{removed:,} products removed over {removed_days} days ago')
    return events, removed


def compact(conn, ceiling_mb=495.0, log=log):
    """Rebuild indexes, then tables, smallest first, while each fits under the ceiling.
    Returns (rebuilt, skipped) lists of names."""
    rebuilt, skipped = [], []
    indexes = conn.execute("""
        select i.indexrelid::regclass::text, pg_relation_size(i.indexrelid)
        from pg_index i join pg_class c on c.oid = i.indrelid join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' order by 2""").fetchall()
    for name, size in indexes:
        if database_mb(conn) + size / 1048576 > ceiling_mb:
            skipped.append(name)
            continue
        conn.execute(f'reindex index {name}')
        rebuilt.append(name)
    tables = conn.execute("""
        select c.oid::regclass::text, pg_total_relation_size(c.oid)
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind = 'r' order by 2""").fetchall()
    for name, size in tables:
        if database_mb(conn) + size / 1048576 > ceiling_mb:
            skipped.append(name)
            continue
        conn.execute(f'vacuum (full, analyze) {name}')
        rebuilt.append(name)
    log(f'compact: rebuilt {len(rebuilt)}; skipped for room ({ceiling_mb:.0f} MB ceiling): '
        f'{", ".join(skipped) or "none"}')
    return rebuilt, skipped


def print_sizes(conn):
    rows = conn.execute("""
        select c.relname, pg_total_relation_size(c.oid), pg_indexes_size(c.oid), s.n_dead_tup
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        left join pg_stat_user_tables s on s.relid = c.oid
        where n.nspname = 'public' and c.relkind = 'r' order by 2 desc limit 10""").fetchall()
    for name, total, indexes, dead in rows:
        print(f'{name:<18} {total / 1048576:>8.1f} MB  (indexes {indexes / 1048576:>6.1f} MB, dead rows {dead or 0:,})')
    print(f'{"database":<18} {database_mb(conn):>8.1f} MB')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compact', action='store_true', help='Also rebuild indexes and tables that fit')
    parser.add_argument('--stats', action='store_true', help='Print sizes and exit')
    args = parser.parse_args()
    url = os.environ.get('DATABASE_URL')
    if not url:
        sys.exit('DATABASE_URL is not set')
    with psycopg.connect(url, autocommit=True) as conn:
        if args.stats:
            print_sizes(conn)
            return 0
        before = database_mb(conn)
        trim_products(conn)
        apply_retention(conn, int(os.environ.get('EVENTS_KEEP_DAYS') or 90),
                        int(os.environ.get('REMOVED_KEEP_DAYS') or 60))
        if args.compact:
            compact(conn, float(os.environ.get('COMPACT_MAX_DB_MB') or 495))
        log(f'database size: {before:.0f} MB before, {database_mb(conn):.0f} MB after')
        print_sizes(conn)
    return 0


if __name__ == '__main__':
    sys.exit(main())
