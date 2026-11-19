"""Watchlist: phone registration under an anonymous account, the watch triggers, and the alerts
written and pushed after a run."""
import unittest
import uuid
from contextlib import contextmanager

import psycopg

from pipeline import ingest, notify_watches
from pipeline.tests.support import DatabaseTest, T0, day, product, snapshot, variant
from pipeline.tests.test_notify_run import FakeExpo

ALICE_TOKEN = 'ExponentPushToken[alice000000000001]'
BOB_TOKEN = 'ExponentPushToken[bob00000000000002]'


class WatchTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        self.acme = self.brand('acme')
        ingest.ingest_snapshot(self.conn, self.acme, 'c1', snapshot({
            'p1': product({'v1': variant(500000)}, title='Lawn Kurta'),
            'p2': product({'v1': variant(300000)}, title='Denim Jacket', type='Jackets'),
            'p3': product({'v1': variant(200000)}, title='Wool Cap'),
        }), now=T0)
        self.ids = dict(self.conn.execute('select external_id, id from products').fetchall())
        self.alice, self.bob = uuid.uuid4(), uuid.uuid4()
        for user in (self.alice, self.bob):
            self.conn.execute('insert into auth.users (id) values (%s)', (user,))

    @contextmanager
    def as_user(self, user):
        with self.conn.transaction():
            self.conn.execute('set local role authenticated')
            self.conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(user) if user else '',))
            yield self.conn

    def watch(self, user, external_id):
        with self.as_user(user) as conn:
            conn.execute('insert into watches (product_id) values (%s)', (self.ids[external_id],))

    def register(self, user, token):
        with self.as_user(user) as conn:
            conn.execute("select register_my_device(%s, 'android', '1.0.0')", (token,))

    def run_day(self, products, sha='c2', at=None):
        at = at or day(1)
        since = self.conn.execute('select now()').fetchone()[0]
        ingest.ingest_snapshot(self.conn, self.acme, sha, snapshot(products, at=at), now=at)
        return since

    def test_register_my_device(self):
        self.register(self.alice, ALICE_TOKEN)
        self.assertEqual(self.conn.execute('select user_id, platform from devices').fetchall(), [(self.alice, 'android')])
        self.register(self.bob, ALICE_TOKEN)  # same phone, new anonymous account after a reinstall
        self.assertEqual(self.conn.execute('select user_id from devices').fetchall(), [(self.bob,)])
        with self.assertRaises(psycopg.errors.InvalidAuthorizationSpecification):
            self.register(None, BOB_TOKEN)
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.register(self.alice, 'not-a-token')

    def test_watch_records_the_price_and_is_private(self):
        self.watch(self.alice, 'p1')
        self.assertEqual(self.scalar('select price_at_watch from watches'), 500000)
        with self.as_user(self.bob) as conn:
            self.assertEqual(conn.execute('select count(*) from watches').fetchone()[0], 0)

    def test_watchlist_limit(self):
        many = {f'x{i}': product(title=f'Item {i}') for i in range(300)}
        many.update({'p1': product({'v1': variant(500000)}, title='Lawn Kurta')})
        ingest.ingest_snapshot(self.conn, self.acme, 'c-many', snapshot(many, at=day(1)), now=day(1), force=True)
        ids = [row[0] for row in self.conn.execute("select id from products where external_id like 'x%' order by id")]
        with self.as_user(self.alice) as conn:
            for pid in ids:
                conn.execute('insert into watches (product_id) values (%s)', (pid,))
        with self.assertRaises(psycopg.errors.ProgramLimitExceeded):
            self.watch(self.alice, 'p1')

    def test_alerts_are_written_once_and_pushed_per_user(self):
        self.watch(self.alice, 'p1')
        self.watch(self.bob, 'p1')
        self.watch(self.bob, 'p2')
        self.register(self.alice, ALICE_TOKEN)
        self.register(self.bob, BOB_TOKEN)
        since = self.run_day({'p1': product({'v1': variant(400000)}, title='Lawn Kurta'),
                              'p2': product({'v1': variant(300000, available=False)}, title='Denim Jacket', type='Jackets'),
                              'p3': product({'v1': variant(100000)}, title='Wool Cap')})
        expo = FakeExpo()
        self.assertEqual(notify_watches.notify_watchers(self.conn, since, log=lambda m: None, post=expo), 3)
        pushes = {call[0]['to']: call[0] for call in expo.calls}
        self.assertEqual(pushes[ALICE_TOKEN]['title'], 'Acme: Lawn Kurta')
        self.assertEqual(pushes[ALICE_TOKEN]['body'], 'Price drop 20%: PKR 5,000 → PKR 4,000')
        self.assertEqual(pushes[ALICE_TOKEN]['data'], {'url': f'/product/{self.ids["p1"]}'})
        self.assertEqual(pushes[BOB_TOKEN]['title'], '2 watched articles changed')
        self.assertEqual(pushes[BOB_TOKEN]['data'], {'url': '/watchlist'})
        self.assertEqual(self.scalar("select count(*) from notifications where status = 'sent'"), 3)
        with self.as_user(self.alice) as conn:
            inbox = conn.execute('select kind, title from notifications').fetchall()
        self.assertEqual(inbox, [('price_drop', 'Acme: Lawn Kurta')])
        # A re-run over the same scan adds nothing.
        self.assertEqual(notify_watches.notify_watchers(self.conn, since, log=lambda m: None, post=FakeExpo()), 0)

    def test_alerts_without_a_phone_are_held(self):
        self.watch(self.alice, 'p1')
        since = self.run_day({'p1': product({'v1': variant(400000)}, title='Lawn Kurta'),
                              'p2': product({'v1': variant(300000)}, title='Denim Jacket', type='Jackets'),
                              'p3': product({'v1': variant(200000)}, title='Wool Cap')})
        expo = FakeExpo()
        notify_watches.notify_watchers(self.conn, since, log=lambda m: None, post=expo)
        self.assertEqual(expo.calls, [])
        self.assertEqual(self.scalar('select status from notifications'), 'held')

    def test_removed_article_alerts_and_old_changes_do_not(self):
        self.watch(self.alice, 'p3')
        self.register(self.alice, ALICE_TOKEN)
        since = self.run_day({'p1': product({'v1': variant(500000)}, title='Lawn Kurta'),
                              'p2': product({'v1': variant(300000)}, title='Denim Jacket', type='Jackets')},
                             at=self.conn.execute('select now()').fetchone()[0])
        expo = FakeExpo()
        notify_watches.notify_watchers(self.conn, since, log=lambda m: None, post=expo)
        self.assertEqual(expo.calls[0][0]['body'], 'Removed from the store')

    def test_deleting_the_account_removes_its_alerts(self):
        self.watch(self.alice, 'p1')
        since = self.run_day({'p1': product({'v1': variant(400000)}, title='Lawn Kurta'),
                              'p2': product({'v1': variant(300000)}, title='Denim Jacket', type='Jackets'),
                              'p3': product({'v1': variant(200000)}, title='Wool Cap')})
        notify_watches.notify_watchers(self.conn, since, log=lambda m: None, post=FakeExpo())
        self.conn.execute('delete from auth.users where id = %s', (self.alice,))
        self.assertEqual(self.scalar('select count(*) from notifications'), 0)


class AlertTextTests(unittest.TestCase):
    def test_texts(self):
        text = notify_watches.alert_text
        self.assertEqual(text('price_rise', 'Kurta', 'Acme', {'price': 400000}, {'price': 500000}),
                         ('Acme: Kurta', 'Price rise 25%: PKR 4,000 → PKR 5,000'))
        self.assertEqual(text('back_in_stock', 'Kurta', 'Acme', None, {'price': 199950})[1], 'Back in stock at PKR 1,999.50')
        self.assertEqual(text('sale_started', 'Kurta', 'Acme', None, {'discount_pct': 30})[1], 'Sale started, 30% off')
        self.assertEqual(text('out_of_stock', 'Kurta', 'Acme', None, None)[1], 'Sold out')

    def test_summary_push(self):
        alerts = [(1, 'u', 10, 'Acme: Kurta', 'x'), (2, 'u', 11, 'Acme: Jacket', 'y'), (3, 'u', 12, 'Acme: Cap', 'z')]
        self.assertEqual(notify_watches.push_for_user(alerts),
                         ('3 watched articles changed', 'Kurta, Jacket and 1 more.', '/watchlist'))


if __name__ == '__main__':
    unittest.main()
