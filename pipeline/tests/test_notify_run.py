"""The "new data is in" push: phone registration and the message sent after a run."""
import unittest
from datetime import timedelta

import psycopg

from pipeline import ingest, notify_run
from pipeline.tests.support import DatabaseTest, T0, day, product, snapshot, variant

TOKEN = 'ExponentPushToken[abcdefghij123456]'


class FakeExpo:
    """Stands in for the Expo push endpoint; answers DeviceNotRegistered for listed tokens."""

    def __init__(self, gone=()):
        self.calls = []
        self.gone = set(gone)

    def __call__(self, url, messages, token):
        self.calls.append(messages)
        return {'data': [{'status': 'error', 'message': 'gone', 'details': {'error': 'DeviceNotRegistered'}}
                         if message['to'] in self.gone else {'status': 'ok', 'id': 'x'} for message in messages]}


class RegisterDeviceTests(DatabaseTest):
    def call_as_anon(self, *args):
        with self.conn.transaction():
            self.conn.execute('set local role anon')
            self.conn.execute('select register_device(%s, %s, %s)', args)

    def test_anon_can_register_but_not_read(self):
        self.call_as_anon(TOKEN, 'android', '1.0.0')
        self.call_as_anon(TOKEN, 'android', '1.0.1')
        rows = self.conn.execute('select push_token, platform, app_version from broadcast_devices').fetchall()
        self.assertEqual(rows, [(TOKEN, 'android', '1.0.1')])
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.conn.transaction():
                self.conn.execute('set local role anon')
                self.conn.execute('select * from broadcast_devices')

    def test_rejects_things_that_are_not_push_tokens(self):
        for bad in (None, '', 'hello', 'ExponentPushToken[]', "ExponentPushToken[x'; drop table x;--]"):
            with self.subTest(bad), self.assertRaises(psycopg.errors.InvalidParameterValue):
                self.call_as_anon(bad, 'android', None)
        self.assertEqual(self.scalar('select count(*) from broadcast_devices'), 0)

    def test_unknown_platform_is_stored_as_null(self):
        self.call_as_anon(TOKEN, 'windows', None)
        self.assertIsNone(self.scalar('select platform from broadcast_devices'))


class NotifyAfterRunTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        self.brand_a, self.brand_b = self.brand('acme'), self.brand('zed')
        for brand in (self.brand_a, self.brand_b):
            ingest.ingest_snapshot(self.conn, brand, 'c1', snapshot({'p1': product({'v1': variant(500000)}),
                                                                     'p2': product({'v1': variant(300000, available=False)})}),
                                   now=T0)
        self.since = self.conn.execute('select now()').fetchone()[0]
        self.conn.execute("insert into broadcast_devices (push_token, platform) values (%s, 'android')", (TOKEN,))

    def run_day(self, brand, sha, p1_price, p2_available, notifiable=True):
        at = day(1)
        ingest.ingest_snapshot(self.conn, brand, sha, snapshot({
            'p1': product({'v1': variant(p1_price)}), 'p2': product({'v1': variant(300000, available=p2_available)}),
        }, at=at), now=at if notifiable else at + timedelta(days=3))

    def test_summary_message(self):
        self.run_day(self.brand_a, 'c2', 400000, True)
        self.run_day(self.brand_b, 'c2', 500000, True)
        expo = FakeExpo()
        self.assertEqual(notify_run.notify_after_run(self.conn, self.since, log=lambda m: None, post=expo), 1)
        message = expo.calls[0][0]
        self.assertEqual(message['to'], TOKEN)
        self.assertEqual(message['title'], 'New prices and stock are in')
        self.assertEqual(message['body'], '3 changes across 2 brands: 1 price drop, 2 back in stock.')
        self.assertEqual(message['data'], {'url': '/changes'})

    def test_run_without_changes_still_says_it_checked(self):
        self.run_day(self.brand_a, 'c2', 500000, False)
        expo = FakeExpo()
        notify_run.notify_after_run(self.conn, self.since, log=lambda m: None, post=expo)
        self.assertEqual(expo.calls[0][0]['body'], 'Checked 1 brand: no changes this time.')

    def test_backfilled_changes_are_not_counted(self):
        self.run_day(self.brand_a, 'c2', 400000, True, notifiable=False)
        expo = FakeExpo()
        notify_run.notify_after_run(self.conn, self.since, log=lambda m: None, post=expo)
        self.assertEqual(expo.calls[0][0]['body'], 'Checked 1 brand: no changes this time.')

    def test_nothing_loaded_sends_nothing(self):
        expo = FakeExpo()
        self.assertEqual(notify_run.notify_after_run(self.conn, self.since, log=lambda m: None, post=expo), 0)
        self.assertEqual(expo.calls, [])

    def test_unregistered_phones_are_removed(self):
        other = 'ExponentPushToken[zzzzzzzzzz999999]'
        self.conn.execute('insert into broadcast_devices (push_token) values (%s)', (other,))
        self.run_day(self.brand_a, 'c2', 400000, True)
        expo = FakeExpo(gone={TOKEN})
        self.assertEqual(notify_run.notify_after_run(self.conn, self.since, log=lambda m: None, post=expo), 1)
        self.assertEqual(self.conn.execute('select push_token from broadcast_devices').fetchall(), [(other,)])

    def test_batches_of_100(self):
        tokens = [f'ExponentPushToken[token{i:06d}xx]' for i in range(250)]
        expo = FakeExpo()
        sent, gone = notify_run.send(tokens, 't', 'b', post=expo)
        self.assertEqual((sent, gone), (250, []))
        self.assertEqual([len(call) for call in expo.calls], [100, 100, 50])


if __name__ == '__main__':
    unittest.main()
