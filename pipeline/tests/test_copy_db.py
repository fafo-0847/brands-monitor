import psycopg
from psycopg import conninfo

from pipeline import copy_db, ingest
from pipeline.tests.support import ADMIN_URL, BOOTSTRAP, DatabaseTest, T0, day, product, snapshot, variant

TARGET = 'stockwatch_copy_test'


def quiet(message):
    pass


class CopyDatabaseTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(f'drop database if exists {TARGET} with (force)')
            admin.execute(f'create database {TARGET}')
        self.target = psycopg.connect(conninfo.make_conninfo(ADMIN_URL, dbname=TARGET,
                                                             options='-c search_path=public,extensions'),
                                      autocommit=True)
        self.target.execute(BOOTSTRAP.read_text(encoding='utf-8'))

    def tearDown(self):
        self.target.close()
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(f'drop database if exists {TARGET} with (force)')

    def seed(self):
        brand = self.brand()
        ingest.ingest_snapshot(self.conn, brand, 'c1', snapshot({'p1': product({'v1': variant(500000)}),
                                                                'p2': product()}), now=T0)
        ingest.ingest_snapshot(self.conn, brand, 'c2', snapshot({'p1': product({'v1': variant(400000)}),
                                                                'p2': product()}, at=day(1)), now=day(1))
        user = self.conn.execute('insert into auth.users default values returning id').fetchone()[0]
        product_id = self.scalar("select id from products where external_id = 'p1'")
        self.conn.execute('insert into watches (user_id, product_id) values (%s, %s)', (user, product_id))
        self.conn.execute("insert into broadcast_devices (push_token) values ('ExponentPushToken[abcdefghij]')")
        return product_id

    def table(self, conn, query):
        return conn.execute(query).fetchall()

    def test_copies_every_row_and_ids(self):
        product_id = self.seed()
        counts = copy_db.copy_database(self.conn, self.target, log=quiet)
        for query in ('select id, external_id, price_min from products order by id',
                      'select id, product_id, price from variants order by id',
                      'select variant_id, observed_at, price from price_points order by 1, 2',
                      'select id, kind, product_id, scan_id from product_events order by id',
                      'select brand_id, last_commit_sha from ingest_cursor',
                      'select push_token from broadcast_devices'):
            self.assertEqual(self.table(self.target, query), self.table(self.conn, query), query)
        self.assertEqual(counts['products'], 2)
        self.assertEqual(self.table(self.target, 'select product_id from private.moved_watches'), [(product_id,)])
        # Accounts stay behind with the old project.
        self.assertEqual(self.target.execute('select count(*) from public.watches').fetchone()[0], 0)

    def test_new_rows_continue_after_copied_ids(self):
        self.seed()
        copy_db.copy_database(self.conn, self.target, log=quiet)
        top = self.scalar('select max(id) from scans')
        brand = self.target.execute('select id, slug, name, granularity from brands').fetchone()
        ingest.ingest_snapshot(self.target, dict(zip(('id', 'slug', 'name', 'granularity'), brand)), 'c3',
                               snapshot({'p1': product({'v1': variant(300000)}), 'p2': product()}, at=day(2)),
                               now=day(2))
        self.assertEqual(self.target.execute('select max(id) from scans').fetchone()[0], top + 1)

    def test_refuses_a_database_that_already_has_products(self):
        self.seed()
        copy_db.copy_database(self.conn, self.target, log=quiet)
        with self.assertRaises(SystemExit):
            copy_db.copy_database(self.conn, self.target, log=quiet)

    def test_first_account_claims_the_moved_watches(self):
        self.seed()
        copy_db.copy_database(self.conn, self.target, log=quiet)
        t = self.target
        self.assertTrue(t.execute('select public.moved_watches_waiting()').fetchone()[0])
        user = t.execute('insert into auth.users default values returning id').fetchone()[0]
        t.execute("select set_config('request.jwt.claim.sub', %s, false)", (str(user),))
        self.assertEqual(t.execute('select public.claim_moved_watches()').fetchone()[0], 1)
        self.assertEqual(t.execute('select count(*) from public.watches where user_id = %s', (user,)).fetchone()[0], 1)
        self.assertFalse(t.execute('select public.moved_watches_waiting()').fetchone()[0])
        self.assertEqual(t.execute('select public.claim_moved_watches()').fetchone()[0], 0)
