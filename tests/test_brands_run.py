"""brands/run.py: the MONITOR_EMAIL switch. Email off must still save the baseline; email on keeps
the rule that a failed email leaves the baseline untouched."""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from brands import run


def snapshot(price):
    return {'schema_version': 1, 'source': 'https://acme.example/collections/all', 'currency': 'PKR',
            'price_unit': 'minor_units', 'checked_at': '2026-11-17T01:00:00+00:00',
            'products': {'p1': {'id': 'p1', 'title': 'Kurta', 'handle': 'kurta', 'url': 'https://acme.example/p/kurta',
                                'vendor': None, 'type': None, 'description': None, 'tags': [], 'images': [],
                                'options': None, 'available': True,
                                'variants': {'v1': {'id': 'v1', 'title': 'M', 'options': ['M'], 'sku': None,
                                                    'available': True, 'price': price, 'compare_at_price': None}}}}}


class EmailSwitchTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.state = self.dir / 'state.json'
        self.report = self.dir / 'changes.json'
        self.state.write_text(json.dumps(snapshot(500000)), encoding='utf-8')
        module = types.ModuleType('brands.scrapers.fake_acme')
        module.scrape = lambda **kwargs: snapshot(400000)
        sys.modules['brands.scrapers.fake_acme'] = module
        self.addCleanup(sys.modules.pop, 'brands.scrapers.fake_acme', None)
        self.config = {'name': 'Acme', 'module': 'fake_acme', 'all_products_url': 'https://acme.example/collections/all'}
        self.args = SimpleNamespace(state=self.state, report=self.report, limit=None, pause=0, dry_run=False,
                                    email_on_first_run=False)

    def saved_price(self):
        data = json.loads(self.state.read_text(encoding='utf-8'))
        return data['products']['p1']['variants']['v1']['price']

    def test_email_off_saves_without_sending(self):
        with mock.patch.dict(os.environ, {'MONITOR_EMAIL': 'off'}), mock.patch.object(run, 'notify') as notify, \
                mock.patch.object(run, 'log'):
            report = run.run_brand('acme', self.config, self.args, 'acme')
        notify.assert_not_called()
        self.assertEqual(report['change_count'], 1)
        self.assertEqual(self.saved_price(), 400000)
        self.assertTrue(self.report.exists())

    def test_email_on_failure_keeps_the_old_baseline(self):
        playwright = mock.MagicMock()
        fake_sync = mock.MagicMock(return_value=playwright)
        with mock.patch.dict(os.environ, {'MONITOR_EMAIL': 'on'}), \
                mock.patch.object(run, 'notify', side_effect=ValueError('Resend rejected email')), \
                mock.patch.object(run, 'log'), \
                mock.patch.dict(sys.modules, {'playwright.sync_api': SimpleNamespace(sync_playwright=fake_sync)}):
            with self.assertRaises(ValueError):
                run.run_brand('acme', self.config, self.args, 'acme')
        self.assertEqual(self.saved_price(), 500000)
        self.assertFalse(self.report.exists())

    def test_switch_values(self):
        for value, expected in (('off', False), ('OFF', False), ('0', False), ('false', False), ('on', True), ('', True)):
            with self.subTest(value), mock.patch.dict(os.environ, {'MONITOR_EMAIL': value}):
                self.assertEqual(run.email_enabled(), expected)
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(run.email_enabled())


if __name__ == '__main__':
    unittest.main()
