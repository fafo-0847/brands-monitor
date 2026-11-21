"""Copy the app database into a new, empty Supabase project.

    SOURCE_DATABASE_URL=<old project> DATABASE_URL=<new project> python -m pipeline.copy_db

Applies the migrations to the new database, then streams every catalog and pipeline table across
with COPY, inside one transaction (a failure leaves the new database empty, so it can simply be
run again). The copy is smaller than the source because it leaves behind the dead space that
VACUUM marks reusable but never hands back. The source is only read, from one consistent snapshot.

Accounts are not copied: anonymous sign-ins belong to the old project, and the phone starts a new
one when the app points at the new project. Watched articles are parked in private.moved_watches
and the first account to open the watchlist takes them over (claim_moved_watches). Alert history
is not copied.
"""
import os
import sys
import time

import psycopg
from psycopg import sql

from pipeline import migrate

# Parents before children, so every foreign key is satisfied as rows arrive.
TABLES = ('brands', 'pipeline_meta', 'scans', 'ingest_cursor', 'products', 'variants', 'price_points',
          'stock_points', 'product_events', 'broadcast_devices')
WATCH_COLUMNS = ('product_id', 'variant_id', 'on_restock', 'on_price_drop', 'on_any_price', 'price_at_watch',
                 'created_at')


def log(message):
    print(time.strftime('%H:%M:%S'), message, flush=True)


def columns(conn, table):
    """Stored, non-generated columns in table order."""
    rows = conn.execute("""select column_name from information_schema.columns
                           where table_schema = 'public' and table_name = %s and is_generated = 'NEVER'
                           order by ordinal_position""", (table,)).fetchall()
    return [row[0] for row in rows]


def copy_rows(src, dst, select, target, names):
    """Stream rows from a query on src into target (a table identifier) on dst."""
    fields = sql.SQL(', ').join(map(sql.Identifier, names))
    with src.cursor().copy(sql.SQL('copy ({}) to stdout').format(select)) as out, \
            dst.cursor().copy(sql.SQL('copy {} ({}) from stdin').format(target, fields)) as into:
        for chunk in out:
            into.write(chunk)


def database_mb(conn):
    return conn.execute('select pg_database_size(current_database())').fetchone()[0] / 1048576


def copy_database(src, dst, log=log):
    """Copy into dst (migrated, empty) from src. Both are autocommit connections."""
    migrate.apply(dst, log=log)
    if dst.execute('select exists (select 1 from public.products)').fetchone()[0]:
        raise SystemExit('The new database already holds products; refusing to copy over them.')

    counts = {}
    with src.transaction(), dst.transaction():
        src.execute('set transaction isolation level repeatable read, read only')
        for conn in (src, dst):
            conn.execute("set local statement_timeout = 0")
        for table in TABLES:
            names = [name for name in columns(dst, table) if name in set(columns(src, table))]
            fields = sql.SQL(', ').join(map(sql.Identifier, names))
            copy_rows(src, dst, sql.SQL('select {} from public.{}').format(fields, sql.Identifier(table)),
                      sql.Identifier('public', table), names)
            source_rows = src.execute(sql.SQL('select count(*) from public.{}').format(sql.Identifier(table))).fetchone()[0]
            copied = dst.execute(sql.SQL('select count(*) from public.{}').format(sql.Identifier(table))).fetchone()[0]
            if copied != source_rows:
                raise RuntimeError(f'{table}: copied {copied} of {source_rows} rows')
            counts[table] = copied
            log(f'{table:<18} {copied:>10,} rows')

        watch_fields = sql.SQL(', ').join(map(sql.Identifier, WATCH_COLUMNS))
        copy_rows(src, dst, sql.SQL('select {} from public.watches').format(watch_fields),
                  sql.Identifier('private', 'moved_watches'), WATCH_COLUMNS)
        counts['moved_watches'] = dst.execute('select count(*) from private.moved_watches').fetchone()[0]
        log(f'{"watched articles":<18} {counts["moved_watches"]:>10,} waiting for the app to claim them')

        # Identity columns keep counting from where the source stopped.
        for table in TABLES:
            if 'id' in columns(dst, table) and dst.execute(
                    "select pg_get_serial_sequence(%s, 'id') is not null", (f'public.{table}',)).fetchone()[0]:
                dst.execute(sql.SQL("select setval(pg_get_serial_sequence({}, 'id'), coalesce(max(id), 0) + 1, false) "
                                    'from public.{}').format(sql.Literal(f'public.{table}'), sql.Identifier(table)))

    for table in TABLES:
        dst.execute(sql.SQL('analyze public.{}').format(sql.Identifier(table)))
    return counts


def main():
    source_url = os.environ.get('SOURCE_DATABASE_URL')
    target_url = os.environ.get('DATABASE_URL')
    if not source_url or not target_url:
        sys.exit('Set SOURCE_DATABASE_URL (the old project) and DATABASE_URL (the new, empty project).')
    if source_url == target_url:
        sys.exit('SOURCE_DATABASE_URL and DATABASE_URL are the same database.')
    with psycopg.connect(source_url, autocommit=True) as src, psycopg.connect(target_url, autocommit=True) as dst:
        before = database_mb(src)
        copy_database(src, dst)
        log(f'done: source {before:.0f} MB, new database {database_mb(dst):.0f} MB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
