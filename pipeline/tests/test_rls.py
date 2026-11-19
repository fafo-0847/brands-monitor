"""Row-level security: what the app's anon and signed-in roles can and cannot do."""
import unittest
import uuid
from contextlib import contextmanager

import psycopg

from pipeline import ingest
from pipeline.tests.support import DatabaseTest, T0, product, snapshot


class RlsTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        self.visible = self.brand('acme')
        self.hidden = self.brand('secret', visible=False)
        ingest.ingest_snapshot(self.conn, self.visible, 'c1', snapshot({'p1': product()}), now=T0)
        self.product_id = self.scalar('select id from products')
        self.alice, self.bob = uuid.uuid4(), uuid.uuid4()
        for user in (self.alice, self.bob):
            self.conn.execute('insert into auth.users (id) values (%s)', (user,))

    @contextmanager
    def as_role(self, role, user=None):
        with self.conn.transaction(force_rollback=False):
            self.conn.execute(f'set local role {role}')
            self.conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(user) if user else '',))
            yield self.conn

    def denied(self, role, user, query, params=None):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.as_role(role, user) as conn:
                conn.execute(query, params)

    def test_signup_creates_a_profile(self):
        self.assertEqual(self.scalar('select count(*) from profiles'), 2)

    def test_anon_reads_catalog_but_not_hidden_brands_or_pipeline_tables(self):
        with self.as_role('anon') as conn:
            self.assertEqual(conn.execute('select slug from brands').fetchall(), [('acme',)])
            self.assertEqual(conn.execute('select count(*) from products').fetchone()[0], 1)
            self.assertEqual(conn.execute('select count(*) from variants').fetchone()[0], 1)
        for table in ('scans', 'ingest_cursor', 'brand_health', 'watches', 'profiles', 'devices', 'notifications',
                      'brand_follows'):
            with self.subTest(table):
                self.denied('anon', None, f'select * from {table}')

    def test_nobody_but_the_pipeline_writes_the_catalog(self):
        for role, user in (('anon', None), ('authenticated', self.alice)):
            with self.subTest(role):
                self.denied(role, user, "update products set title = 'hacked'")
                self.denied(role, user, 'delete from variants')
                self.denied(role, user, 'insert into product_events (brand_id, product_id, kind, observed_at, scan_id) '
                                        "values (1, 1, 'price_drop', now(), 1)")

    def test_users_see_and_change_only_their_own_rows(self):
        with self.as_role('authenticated', self.alice) as conn:
            conn.execute('insert into watches (product_id) values (%s)', (self.product_id,))
            conn.execute('insert into brand_follows (brand_id) values (%s)', (self.visible['id'],))
            conn.execute("insert into devices (push_token, platform) values ('alice-token', 'android')")
        with self.as_role('authenticated', self.bob) as conn:
            for table in ('watches', 'brand_follows', 'devices', 'notifications'):
                self.assertEqual(conn.execute(f'select count(*) from {table}').fetchone()[0], 0, table)
            self.assertEqual(conn.execute('select count(*) from profiles').fetchone()[0], 1)
            self.assertEqual(conn.execute('delete from watches').rowcount, 0)
            self.assertEqual(conn.execute('update devices set platform = %s', ('ios',)).rowcount, 0)
        self.assertEqual(self.scalar('select user_id from watches'), self.alice)
        self.assertEqual(self.scalar('select platform from devices'), 'android')

    def test_user_cannot_create_rows_for_someone_else(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.as_role('authenticated', self.bob) as conn:
                conn.execute('insert into watches (user_id, product_id) values (%s, %s)', (self.alice, self.product_id))

    def test_duplicate_product_watch_is_refused(self):
        with self.as_role('authenticated', self.alice) as conn:
            conn.execute('insert into watches (product_id) values (%s)', (self.product_id,))
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.as_role('authenticated', self.alice) as conn:
                conn.execute('insert into watches (product_id) values (%s)', (self.product_id,))

    def test_inbox_is_read_only_except_for_marking_read(self):
        self.conn.execute("insert into notifications (user_id, kind, title) values (%s, 'price_drop', 'Hello')",
                          (self.alice,))
        with self.as_role('authenticated', self.alice) as conn:
            self.assertEqual(conn.execute('update notifications set read_at = now()').rowcount, 1)
        self.denied('authenticated', self.alice, "update notifications set title = 'x'")
        self.denied('authenticated', self.alice, 'delete from notifications')
        self.denied('authenticated', self.alice,
                    "insert into notifications (user_id, kind, title) values (%s, 'x', 'x')", (self.alice,))
        with self.as_role('authenticated', self.bob) as conn:
            self.assertEqual(conn.execute('update notifications set read_at = null').rowcount, 0)

    def test_deleting_the_account_removes_all_user_data(self):
        with self.as_role('authenticated', self.alice) as conn:
            conn.execute('insert into watches (product_id) values (%s)', (self.product_id,))
            conn.execute("insert into devices (push_token) values ('alice-token')")
        self.conn.execute('delete from auth.users where id = %s', (self.alice,))
        for table in ('watches', 'devices'):
            self.assertEqual(self.scalar(f'select count(*) from {table}'), 0)
        self.assertEqual(self.scalar('select count(*) from profiles'), 1)


if __name__ == '__main__':
    unittest.main()
