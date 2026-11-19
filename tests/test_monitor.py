import copy
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import monitor as m


def product():
    return m.normalize_product({'id': 123, 'title': 'Denim <Jacket>', 'handle': 'jacket',
                                'variants': [{'id': 456, 'title': 'M', 'options': ['M'],
                                              'available': True, 'price': 199900, 'compare_at_price': 299900}]})


def state(p=None):
    return {'currency': 'PKR', 'products': {'123': p or product()}}


class MonitorTests(unittest.TestCase):
    def test_no_changes(self):
        self.assertEqual(m.changes_between(state(), state()), [])

    def test_stock_and_both_price_directions(self):
        old, new = state(), state()
        new['products']['123']['variants']['456'].update(available=False, price=179900, compare_at_price=399900)
        kinds = {c['kind'] for c in m.changes_between(old, new)}
        self.assertEqual(kinds, {'Sold out', 'Price decreased', 'Compare-at price increased'})
        reverse = {c['kind'] for c in m.changes_between(new, old)}
        self.assertIn('Back in stock', reverse)
        self.assertIn('Price increased', reverse)

    def test_new_and_removed_products(self):
        empty = {'products': {}, 'currency': 'PKR'}
        added = m.changes_between(empty, state())
        self.assertEqual(added[0]['kind'], 'New product')
        self.assertIn('M', added[0]['detail'])
        self.assertEqual(m.changes_between(state(), empty)[0]['kind'], 'Product removed')

    def test_variant_addition_and_removal(self):
        old, new = state(), state()
        v = new['products']['123']['variants'].pop('456')
        v.update(id='789', title='XL')
        new['products']['123']['variants']['789'] = v
        self.assertEqual({c['kind'] for c in m.changes_between(old, new)}, {'Size/option added', 'Size/option removed'})

    def test_escaping_and_variant_link(self):
        old, new = state(), state()
        new['products']['123']['variants']['456']['available'] = False
        changes = m.changes_between(old, new)
        rendered = m.email_body(changes)
        self.assertIn('Denim &lt;Jacket&gt;', rendered)
        self.assertIn('?variant=456', rendered)
        self.assertNotIn('Denim <Jacket>', rendered)

    def test_price_validation(self):
        for invalid in ('1999.00', None, -1, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                m.normalize_product({'id': 123, 'title': 'x', 'handle': 'x', 'variants': [
                    {'id': 456, 'title': 'M', 'options': ['M'], 'available': True, 'price': invalid}]})

    def test_pagination(self):
        page = '<ul id="product-grid"><li><a href="/products/a">a</a></li></ul><a data-kp-next data-kp-total="2" href="/collections/all?page=2">Next</a>'
        handles, url, total = m.parse_collection(page, m.COLLECTION)
        self.assertEqual((handles, total), ({'a'}, 2))
        self.assertEqual(url, m.BASE + '/collections/all?page=2')
        last = '<span id="ProductCountDesktop">2 products</span><ul id="product-grid"><li><a href="/products/b">b</a></li></ul>'
        with patch.object(m, 'get', side_effect=[page, last]):
            self.assertEqual(m.catalog_handles(None, 0), {'a', 'b'})

    def test_live_theme_next_link_has_prev_class(self):
        page = '<span id="ProductCountDesktop">32 products</span><ul id="product-grid"><a href="/products/a">a</a></ul><nav class="pagination"><a aria-label="Next page" class="pagination__item--prev" href="/collections/all?page=2">Next</a></nav>'
        self.assertEqual(m.parse_collection(page, m.COLLECTION)[1], m.BASE + '/collections/all?page=2')
        last = '<span id="ProductCountDesktop">32 products</span><ul id="product-grid"><a href="/products/b">b</a></ul><nav class="pagination"><a aria-label="Previous page" class="pagination__item--next" href="/collections/all?page=1">Previous</a></nav>'
        self.assertIsNone(m.parse_collection(last, m.COLLECTION)[1])

    def test_reject_partial_catalog(self):
        page = '<ul id="product-grid"><a href="/products/a">a</a></ul><span data-kp-total="2"></span>'
        with patch.object(m, 'get', return_value=page), self.assertRaises(ValueError):
            m.catalog_handles(None, 0)
        with self.assertRaises(ValueError):
            m.parse_collection('<html>Blocked</html>', m.COLLECTION)

    def test_outfitters_pagination_without_product_count(self):
        store = m.OUTFITTERS
        path = store.collection_path
        first = f'<ul id="product-grid"><li><a href="{path}/products/jacket?variant=456">Jacket</a></li></ul>'
        first += f'<div id="AjaxinatePagination"><a href="{path}?page=2">Loading...</a></div>'
        last = '<ul id="product-grid"><li><a href="/products/tee">Tee</a></li></ul>'
        with patch.object(m, 'get', side_effect=[first, last]) as fetch:
            self.assertEqual(m.catalog_handles(None, 0, store), {'jacket', 'tee'})
        self.assertEqual(fetch.call_args.args[1], store.source + '?page=2')
        with self.assertRaisesRegex(ValueError, 'skipped a page'):
            m.parse_collection(first.replace('page=2', 'page=3'), store.collection_url, store)

    def test_email_failure_does_not_advance_state(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            old = state()
            old.update(schema_version=1, source=m.BASE + '/collections/all', checked_at='2026-11-06T00:00:00Z')
            m.atomic_json(path, old)
            saved = path.read_bytes()
            new = copy.deepcopy(old)
            new['products']['123']['variants']['456']['price'] = 99900
            with patch('sys.argv', ['monitor.py', '--state', str(path), '--report', str(Path(folder) / 'changes.json')]), \
                 patch.object(m, 'scan', return_value=new), \
                 patch.object(m, 'notify', side_effect=RuntimeError('email failed')), \
                 patch.object(m, 'sync_playwright'):
                with self.assertRaises(RuntimeError):
                    m.main()
            self.assertEqual(path.read_bytes(), saved)

    def test_idempotency_key_stable_and_payload(self):
        pw = MagicMock()
        api = pw.request.new_context.return_value
        response = api.post.return_value
        response.status, response.ok = 200, True
        response.json.return_value = {'id': 'test-id'}
        changes = m.changes_between({'products': {}}, state())
        with patch.dict('os.environ', {'RESEND_API_KEY': 'test', 'EMAIL_FROM': 'x@example.com', 'EMAIL_TO': 'y@example.com'}), patch.object(m.time, 'sleep'):
            m.notify(pw, changes, 'event-1')
            first = api.post.call_args.kwargs
            m.notify(pw, changes, 'event-1')
            self.assertEqual(first['headers'], api.post.call_args.kwargs['headers'])
            self.assertIn('<table', first['data']['html'])
            self.assertEqual(first['data']['to'], ['y@example.com'])


if __name__ == '__main__':
    unittest.main()
