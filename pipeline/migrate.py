"""Apply supabase/migrations/*.sql in order, once each.

    python -m pipeline.migrate            # uses DATABASE_URL
    python -m pipeline.migrate --list

Applied versions are recorded in supabase_migrations.schema_migrations, the same table the
Supabase CLI uses, so `supabase db push` later sees them as already applied.
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parent.parent / 'supabase' / 'migrations'


def pending(conn):
    conn.execute('create schema if not exists supabase_migrations')
    conn.execute('create table if not exists supabase_migrations.schema_migrations '
                 '(version text primary key, statements text[], name text)')
    done = {row[0] for row in conn.execute('select version from supabase_migrations.schema_migrations')}
    files = sorted(MIGRATIONS.glob('*.sql'))
    return [path for path in files if path.name.split('_', 1)[0] not in done]


def apply(conn, log=print):
    for path in pending(conn):
        version, name = path.stem.split('_', 1)
        with conn.transaction():
            conn.execute(path.read_text(encoding='utf-8'))
            conn.execute('insert into supabase_migrations.schema_migrations (version, name) values (%s, %s)',
                         (version, name))
        log(f'applied {path.name}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true', help='Show pending migrations and exit')
    args = parser.parse_args()
    url = os.environ.get('DATABASE_URL')
    if not url:
        sys.exit('DATABASE_URL is not set')
    with psycopg.connect(url, autocommit=True) as conn:
        if args.list:
            for path in pending(conn):
                print(path.name)
            return 0
        apply(conn)
    return 0


if __name__ == '__main__':
    sys.exit(main())
