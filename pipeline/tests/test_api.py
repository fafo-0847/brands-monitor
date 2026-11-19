"""The SQL functions the app calls (supabase/migrations/*_api.sql)."""
import unittest
from datetime import timedelta

import psycopg

from pipeline import ingest
from pipeline.tests.support import DatabaseTest, T0, day, product, snapshot, variant


def kurta(price=300000, **fields):
    return product({'s': variant(price, size='S'), 'm': variant(price, size='M', available=False)}, **fields)


class ApiTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        self.acme = self.brand('acme')
        self.zed = self.brand('zed')
        self.hidden = self.brand('secret', visible=False)
        self.load(self.acme, 'a1', {
            'kurta': kurta(title='Embroidered Lawn Kurta', handle='lawn-kurta'),
            'jacket': product({'v': variant(900000)}, title='Denim Jacket', handle='denim-jacket', type='Jackets',
                              tags=['Men']),
            'shoe': product({'v': variant(500000, available=False, size='42')}, title='Leather Loafers',
                            handle='loafers', type='Shoes', tags=['Men']),
        })
        self.load(self.zed, 'z1', {'kurta': kurta(250000, title='Printed Kurta', handle='printed-kurta')})
        self.load(self.hidden, 'h1', {'kurta': kurta(title='Secret Kurta')})

    def load(self, brand, sha, products, at=T0):
        ingest.ingest_snapshot(self.conn, brand, sha, snapshot(products, at=at), now=at)

    def acme_day(self, sha, at, kurta_item, jacket=900000, shoe_available=False, extra=None):
        products = {
            'kurta': kurta_item,
            'jacket': product({'v': variant(jacket)}, title='Denim Jacket', handle='denim-jacket', type='Jackets',
                              tags=['Men']),
            'shoe': product({'v': variant(500000, available=shoe_available, size='42')}, title='Leather Loafers',
                            handle='loafers', type='Shoes', tags=['Men']),
        }
        products.update(extra or {})
        self.load(self.acme, sha, products, at=at)

    def search(self, **params):
        args = ', '.join(f'{name} => %({name})s' for name in params)
        rows = self.conn.execute(f'select title from search_products({args})', params).fetchall()
        return [row[0] for row in rows]

    def feed(self, kind, **params):
        params['p_kind'] = kind
        args = ', '.join(f'{name} => %({name})s' for name in params)
        return self.conn.execute(f'select title, old_price, new_price from home_feed({args})', params).fetchall()

    def series(self, product_id, variant_id=None, since=None):
        return self.conn.execute('select observed_at, price, compare_at_price, available from price_series(%s, %s, %s)',
                                 (product_id, variant_id, since)).fetchall()

    def test_keyword_search_hides_hidden_brands_and_matches_prefixes(self):
        self.assertCountEqual(self.search(p_query='kurta'), ['Embroidered Lawn Kurta', 'Printed Kurta'])
        self.assertEqual(self.search(p_query='lawn kur'), ['Embroidered Lawn Kurta'])
        self.assertEqual(self.search(p_query='acme jacket'), ['Denim Jacket'])
        self.assertEqual(self.search(p_query='zzzz'), [])

    def test_typos_fall_back_to_fuzzy_title_match(self):
        self.assertEqual(self.search(p_query='loafrs'), ['Leather Loafers'])
        self.assertEqual(self.search(p_query='jaket'), ['Denim Jacket'])

    def test_odd_input_does_not_error(self):
        for text in ("'; drop table products; --", 'the', '   ', '!!!', 'a:*', 'x' * 500, '\\'):
            with self.subTest(text):
                self.search(p_query=text)
        self.assertEqual(self.scalar('select count(*) from products'), 5)

    def test_filters(self):
        self.assertEqual(len(self.search()), 4)
        self.assertCountEqual(self.search(p_in_stock=True), ['Embroidered Lawn Kurta', 'Printed Kurta', 'Denim Jacket'])
        self.assertEqual(self.search(p_brand_ids=[self.zed['id']]), ['Printed Kurta'])
        self.assertCountEqual(self.search(p_genders=['men']), ['Denim Jacket', 'Leather Loafers'])
        self.assertEqual(self.search(p_categories=['footwear']), ['Leather Loafers'])
        self.assertEqual(self.search(p_price_min=400000, p_price_max=600000), ['Leather Loafers'])
        self.assertCountEqual(self.search(p_sizes=['S']), ['Embroidered Lawn Kurta', 'Printed Kurta'])
        self.assertEqual(self.search(p_sizes=['M']), ['Denim Jacket'])  # the kurtas have M, but sold out
        self.assertEqual(self.search(p_query='kurta', p_brand_ids=[self.acme['id']], p_in_stock=True),
                         ['Embroidered Lawn Kurta'])

    def test_sale_filters_and_sorts(self):
        on_sale = product({'s': variant(150000, compare_at=300000, size='S')}, title='Embroidered Lawn Kurta')
        self.acme_day('a2', day(1), on_sale, jacket=810000)
        self.assertEqual(self.search(p_on_sale=True, p_sort='discount'), ['Embroidered Lawn Kurta'])
        self.assertEqual(self.search(p_min_discount=40), ['Embroidered Lawn Kurta'])
        self.assertEqual(self.search(p_min_discount=60), [])
        self.assertEqual(self.search(p_sort='price_asc')[:2], ['Embroidered Lawn Kurta', 'Printed Kurta'])
        self.assertEqual(self.search(p_sort='price_desc')[0], 'Denim Jacket')
        self.assertEqual(set(self.search(p_sort='recent_price_change')[:2]), {'Embroidered Lawn Kurta', 'Denim Jacket'})
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.search(p_sort='id; drop table products')

    def test_paging_is_capped(self):
        self.assertEqual(len(self.search(p_limit=2)), 2)
        self.assertEqual(len(self.search(p_limit=2, p_offset=3)), 1)
        self.assertEqual(len(self.search(p_limit=100000)), 4)
        self.assertEqual(len(self.search(p_limit=-5)), 1)

    def test_removed_products_are_not_found(self):
        ingest.ingest_snapshot(self.conn, self.zed, 'z2', snapshot({'other': product(title='Other Kurta')}, at=day(1)),
                               now=day(1), force=True)
        self.assertNotIn('Printed Kurta', self.search(p_query='kurta'))

    def test_home_feeds(self):
        cap = {'cap': product({'v': variant(90000)}, title='Wool Cap', handle='wool-cap')}
        self.acme_day('a2', day(1), kurta(150000, title='Embroidered Lawn Kurta', handle='lawn-kurta'),
                      jacket=810000, shoe_available=True, extra=cap)
        self.assertEqual(self.feed('price_drops'), [('Embroidered Lawn Kurta', 300000, 150000),
                                                    ('Denim Jacket', 900000, 810000)])
        self.assertEqual([row[0] for row in self.feed('back_in_stock')], ['Leather Loafers'])
        self.assertEqual([row[0] for row in self.feed('new_arrivals')], ['Wool Cap'])
        self.assertEqual(self.feed('price_drops', p_brand_ids=[self.zed['id']]), [])
        self.assertEqual(len(self.feed('price_drops', p_limit=1)), 1)
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.feed('everything')

    def test_price_drop_feed_only_covers_the_latest_days(self):
        self.acme_day('a2', day(1), kurta(200000))
        self.acme_day('a3', day(10), kurta(200000), jacket=800000)
        self.assertEqual([row[1:] for row in self.feed('price_drops')], [(900000, 800000)])

    def test_product_detail(self):
        self.acme_day('a2', day(1), kurta(200000, title='Embroidered Lawn Kurta', handle='lawn-kurta'))
        detail = self.scalar("select product_detail(p_brand_slug => 'acme', p_handle => 'lawn-kurta')")
        self.assertEqual(detail['title'], 'Embroidered Lawn Kurta')
        self.assertEqual(detail['brand']['slug'], 'acme')
        self.assertTrue(detail['brand']['tracks_sizes'])
        self.assertCountEqual([(v['size'], v['available'], v['price']) for v in detail['variants']],
                              [('S', True, 200000), ('M', False, 200000)])
        self.assertEqual(detail['stats']['lowest_price'], 200000)
        self.assertEqual(detail['stats']['highest_price'], 300000)
        self.assertEqual(detail['stats']['price_changes'], 2)
        self.assertEqual(self.scalar('select product_detail(p_id => %s)', (detail['id'],))['handle'], 'lawn-kurta')
        self.assertIsNone(self.scalar('select product_detail(p_id => 999999)'))
        hidden = self.scalar("select id from products where title = 'Secret Kurta'")
        self.assertIsNone(self.scalar('select product_detail(p_id => %s)', (hidden,)))

    def test_product_detail_without_history(self):
        detail = self.scalar("select product_detail(p_brand_slug => 'acme', p_handle => 'denim-jacket')")
        self.assertEqual(detail['stats']['lowest_price'], 900000)
        self.assertEqual(detail['stats']['highest_price'], 900000)
        self.assertEqual(detail['stats']['price_changes'], 0)

    def test_price_series(self):
        def two(s, m, m_available=False):
            return product({'s': variant(s, size='S'), 'm': variant(m, size='M', available=m_available)})
        self.acme_day('a2', day(1), two(300000, 250000))                     # M gets cheaper
        self.acme_day('a3', day(2), two(300000, 250000, m_available=True))   # M restocks
        self.acme_day('a4', day(3), two(200000, 250000, m_available=True))   # S gets cheaper
        pid = self.scalar("select id from products where external_id = 'kurta' and brand_id = %s", (self.acme['id'],))
        self.assertEqual(self.series(pid), [(T0, 300000, None, True), (day(1), 250000, None, True),
                                            (day(2), 250000, None, True), (day(3), 200000, None, True)])
        m = self.scalar("select id from variants where product_id = %s and external_id = 'm'", (pid,))
        self.assertEqual(self.series(pid, m), [(T0, 300000, None, False), (day(1), 250000, None, False),
                                               (day(2), 250000, None, True)])
        self.assertEqual([row[0] for row in self.series(pid, since=day(2) + timedelta(hours=1))], [day(2), day(3)])

    def test_price_series_for_a_product_that_never_changed(self):
        pid = self.scalar("select id from products where title = 'Denim Jacket'")
        self.assertEqual(self.series(pid), [(T0, 900000, None, True)])
        self.assertEqual(self.series(999999), [])

    def test_anonymous_role_can_call_the_api(self):
        with self.conn.transaction():
            self.conn.execute('set local role anon')
            self.assertEqual(len(self.search(p_query='kurta')), 2)
            self.assertEqual(self.feed('new_arrivals'), [])
            pid = self.scalar("select id from products where title = 'Denim Jacket'")
            self.assertEqual(len(self.series(pid)), 1)
            self.assertIsNotNone(self.scalar('select product_detail(p_id => %s)', (pid,)))


if __name__ == '__main__':
    unittest.main()
