"""Shared test plumbing: a throwaway database with the migrations applied.

Set TEST_DATABASE_URL to a superuser URL on a disposable Postgres server that has the
pg_trgm and vector extensions, for example:

    docker run -d --name stockwatch-pg -e POSTGRES_PASSWORD=postgres -p 54329:5432 pgvector/pgvector:pg17
    TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54329/postgres

The tests create and drop their own database (stockwatch_test) on that server.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import conninfo

from pipeline import migrate

ADMIN_URL = os.environ.get('TEST_DATABASE_URL')
DB_NAME = 'stockwatch_test'
BOOTSTRAP = Path(__file__).with_name('local_supabase.sql')
T0 = datetime(2026, 11, 1, 1, 0, tzinfo=timezone.utc)

TABLES = ('notifications', 'devices', 'watches', 'brand_follows', 'profiles', 'product_events', 'price_points',
          'stock_points', 'variants', 'products', 'scans', 'ingest_cursor', 'brands')


def day(n):
    return T0 + timedelta(days=n)


def test_url():
    return conninfo.make_conninfo(ADMIN_URL, dbname=DB_NAME, options='-c search_path=public,extensions')


@unittest.skipUnless(ADMIN_URL, 'TEST_DATABASE_URL is not set')
class DatabaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(f'drop database if exists {DB_NAME} with (force)')
            admin.execute(f'create database {DB_NAME}')
        cls.conn = psycopg.connect(test_url(), autocommit=True)
        cls.conn.execute(BOOTSTRAP.read_text(encoding='utf-8'))
        migrate.apply(cls.conn, log=lambda message: None)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(f'drop database if exists {DB_NAME} with (force)')

    def setUp(self):
        self.conn.execute(f'truncate {", ".join(TABLES)}, auth.users restart identity cascade')

    def brand(self, slug='acme', granularity='variant', visible=True):
        row = self.conn.execute(
            """insert into brands (slug, name, origin_url, strategy, granularity, is_visible)
               values (%s, %s, %s, 'shopify_json', %s, %s) returning id""",
            (slug, slug.title(), f'https://{slug}.example', granularity, visible)).fetchone()
        return {'id': row[0], 'slug': slug, 'name': slug.title(), 'granularity': granularity}

    def scalar(self, query, params=None):
        return self.conn.execute(query, params).fetchone()[0]

    def events(self, level='product'):
        """Sorted (kind, product external id) pairs; level is 'product', 'variant' or 'all'."""
        where = {'product': 'e.variant_id is null', 'variant': 'e.variant_id is not null', 'all': 'true'}[level]
        rows = self.conn.execute(
            f"""select e.kind, p.external_id from product_events e join products p on p.id = e.product_id
                where {where} order by 1, 2""").fetchall()
        return [tuple(row) for row in rows]


def variant(price=100000, available=True, compare_at=None, size='M'):
    return {'title': size, 'options': [size], 'sku': None, 'available': available, 'price': price,
            'compare_at_price': compare_at}


def product(variants=None, **fields):
    variants = variants if variants is not None else {'v1': variant()}
    data = {'title': 'Lawn Kurta', 'handle': 'lawn-kurta', 'url': 'https://acme.example/products/lawn-kurta',
            'vendor': None, 'type': 'Kurta', 'description': 'Soft lawn.', 'tags': ['Women'],
            'images': ['https://cdn.example/a.jpg'], 'options': [{'name': 'Size', 'position': 1, 'values': ['M']}]}
    data.update(fields)
    data['variants'] = {key: dict(value, id=key) for key, value in variants.items()}
    data['available'] = any(v['available'] for v in data['variants'].values())
    return data


def snapshot(products, at=T0, **overrides):
    data = {'schema_version': 1, 'source': 'https://acme.example/collections/all/products.json', 'currency': 'PKR',
            'price_unit': 'minor_units', 'checked_at': at.isoformat(),
            'products': {key: dict(value, id=key) for key, value in products.items()}}
    data.update(overrides)
    return data
