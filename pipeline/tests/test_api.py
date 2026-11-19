"""The SQL functions the app calls (supabase/migrations/*_api.sql)."""
import unittest
from datetime import date, timedelta

import psycopg
from psycopg import conninfo

from pipeline import ingest, migrate
from pipeline.tests.support import ADMIN_URL, BOOTSTRAP, DatabaseTest, T0, day, product, snapshot, test_url, variant


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

    def test_misspelled_words_find_nothing(self):
        # The fuzzy fallback and its trigram index were removed to save space (20261119000001).
        self.assertEqual(self.search(p_query='loafrs'), [])
        self.assertEqual(self.search(p_query='loafers'), ['Leather Loafers'])

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

    def count(self, **params):
        args = ', '.join(f'{name} => %({name})s' for name in params)
        return self.scalar(f'select search_products_count({args})', params)

    def test_count_matches_the_result_list(self):
        cases = [{}, {'p_query': 'kurta'}, {'p_query': 'jaket'}, {'p_in_stock': True}, {'p_out_of_stock': True},
                 {'p_genders': ['men']}, {'p_sizes': ['S']}, {'p_brand_ids': [self.zed['id']]},
                 {'p_query': 'kurta', 'p_in_stock': True, 'p_price_max': 260000}, {'p_query': 'zzzz'},
                 {'p_exclude_brand_ids': [self.acme['id']]}, {'p_exclude_categories': ['eastern']}]
        for params in cases:
            with self.subTest(params):
                self.assertEqual(self.count(**params), len(self.search(p_limit=50, **params)))

    def test_count_stops_at_10001(self):
        many = {'kurta': kurta(250000, title='Printed Kurta', handle='printed-kurta')}
        many.update({f'p{i}': product(title=f'Shirt {i}') for i in range(10050)})
        self.load(self.zed, 'z-many', many, at=day(1))
        self.assertEqual(self.count(p_brand_ids=[self.zed['id']]), 10001)
        self.assertEqual(self.count(p_brand_ids=[self.acme['id']]), 3)

    def test_exclusions(self):
        self.assertEqual(self.search(p_exclude_brand_ids=[self.acme['id']]), ['Printed Kurta'])
        self.assertCountEqual(self.search(p_exclude_categories=['eastern']), ['Denim Jacket', 'Leather Loafers'])
        self.assertEqual(self.search(p_query='kurta', p_exclude_brand_ids=[self.zed['id']]), ['Embroidered Lawn Kurta'])
        self.conn.execute("update products set category = null where title = 'Denim Jacket'")
        self.assertIn('Denim Jacket', self.search(p_exclude_categories=['western']))

    def test_out_of_stock_filter(self):
        self.assertEqual(self.search(p_out_of_stock=True), ['Leather Loafers'])
        self.assertEqual(self.search(p_out_of_stock=True, p_query='kurta'), [])

    def load_changes(self):
        """Nov 2 (Pakistan): two price drops, a restock and a new article at Acme; a hidden brand change.
        Nov 3 01:00 Pakistan (Nov 2 20:00 UTC): Zed's kurta sells out."""
        cap = {'cap': product({'v': variant(90000)}, title='Wool Cap', handle='wool-cap')}
        self.acme_day('a2', day(1), kurta(150000, title='Embroidered Lawn Kurta', handle='lawn-kurta'),
                      jacket=810000, shoe_available=True, extra=cap)
        self.load(self.hidden, 'h2', {'kurta': kurta(100000, title='Secret Kurta')}, at=day(1))
        sold_out = product({'s': variant(250000, size='S', available=False),
                            'm': variant(250000, size='M', available=False)}, title='Printed Kurta')
        self.load(self.zed, 'z2', {'kurta': sold_out}, at=day(1) + timedelta(hours=19))

    def test_change_days_use_pakistan_time(self):
        self.load_changes()
        rows = self.conn.execute('select day, changes from change_days()').fetchall()
        self.assertEqual(rows, [(date(2026, 11, 3), 1), (date(2026, 11, 2), 4)])

    def test_change_summary(self):
        self.load_changes()
        rows = self.conn.execute("select brand_slug, kind, changes from change_summary('2026-11-02')").fetchall()
        self.assertEqual(rows, [('acme', 'back_in_stock', 1), ('acme', 'new_product', 1), ('acme', 'price_drop', 2)])
        self.assertEqual(self.conn.execute("select * from change_summary('2026-11-05')").fetchall(), [])

    def test_recent_changes_filters(self):
        self.load_changes()
        changes = lambda query, params=(): self.conn.execute(query, params).fetchall()
        day_rows = changes("select kind, title from recent_changes(p_day => '2026-11-02') order by kind, title")
        self.assertEqual(day_rows, [('back_in_stock', 'Leather Loafers'), ('new_product', 'Wool Cap'),
                                    ('price_drop', 'Denim Jacket'), ('price_drop', 'Embroidered Lawn Kurta')])
        drops = changes("select title, old_price, new_price from recent_changes(p_day => '2026-11-02', "
                        "p_kinds => array['price_drop']) order by title")
        self.assertEqual(drops, [('Denim Jacket', 900000, 810000), ('Embroidered Lawn Kurta', 300000, 150000)])
        zed = changes('select kind, title, available from recent_changes(p_brand_ids => %s)', ([self.zed['id']],))
        self.assertEqual(zed, [('out_of_stock', 'Printed Kurta', False)])
        self.assertEqual(changes("select * from recent_changes(p_day => '2026-11-01')"), [])
        self.assertEqual(len(changes('select * from recent_changes(p_limit => 2)')), 2)
        self.assertEqual(len(changes('select * from recent_changes()')), 5)


    def test_recent_changes_sorting(self):
        self.load_changes()
        rows = lambda sort: [row[0] for row in self.conn.execute(
            "select title from recent_changes(p_day => '2026-11-02', p_sort => %s)", (sort,)).fetchall()]
        self.assertEqual(rows('biggest_drop')[:2], ['Embroidered Lawn Kurta', 'Denim Jacket'])  # -50% before -10%
        self.assertEqual(rows('price_asc'), ['Wool Cap', 'Embroidered Lawn Kurta', 'Leather Loafers', 'Denim Jacket'])
        self.assertEqual(rows('price_desc'), ['Denim Jacket', 'Leather Loafers', 'Embroidered Lawn Kurta', 'Wool Cap'])
        self.assertEqual(len(rows('recent')), 4)
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            rows('cheapest; drop table products')

    def test_recent_changes_price_filter_and_summary(self):
        self.load_changes()
        args = {'lo': 100000, 'hi': 600000}
        titles = self.conn.execute("select title, price from recent_changes(p_day => '2026-11-02', "
                                   'p_price_min => %(lo)s, p_price_max => %(hi)s) order by title', args).fetchall()
        self.assertEqual(titles, [('Embroidered Lawn Kurta', 150000), ('Leather Loafers', 500000)])
        summary = self.conn.execute("select kind, changes from change_summary('2026-11-02', %(lo)s, %(hi)s) "
                                    'order by kind', args).fetchall()
        self.assertEqual(summary, [('back_in_stock', 1), ('price_drop', 1)])
        self.assertEqual(len(self.conn.execute("select * from change_summary('2026-11-02')").fetchall()), 3)

    def test_recent_changes_category_filter(self):
        self.load_changes()
        titles = self.conn.execute("select title from recent_changes(p_day => '2026-11-02', "
                                   "p_categories => array['footwear', 'western']) order by title").fetchall()
        self.assertEqual([row[0] for row in titles], ['Denim Jacket', 'Leather Loafers'])
        summary = self.conn.execute("select kind, changes from change_summary('2026-11-02', "
                                    "p_categories => array['footwear']) order by kind").fetchall()
        self.assertEqual(summary, [('back_in_stock', 1)])

    def test_changes_stock_gender_and_exclusions(self):
        self.load_changes()
        titles = lambda **kw: sorted(row[0] for row in self.conn.execute(
            'select title from recent_changes(' + ', '.join(f'{k} => %({k})s' for k in kw) + ')', kw).fetchall())
        nov2 = '2026-11-02'
        self.assertEqual(titles(p_day=nov2, p_stock='out'), [])
        self.assertEqual(len(titles(p_day=nov2, p_stock='in')), 4)
        self.assertEqual(titles(p_stock='out'), ['Printed Kurta'])
        self.assertEqual(titles(p_day=nov2, p_genders=['men']), ['Denim Jacket', 'Leather Loafers'])
        self.assertEqual(titles(p_exclude_brand_ids=[self.acme['id']]), ['Printed Kurta'])
        self.assertEqual(titles(p_day=nov2, p_exclude_categories=['footwear', 'western']),
                         ['Embroidered Lawn Kurta', 'Wool Cap'])
        summary = self.conn.execute("select kind, changes from change_summary('2026-11-02', p_genders => array['men']) "
                                    'order by kind').fetchall()
        self.assertEqual(summary, [('back_in_stock', 1), ('price_drop', 1)])
        summary = self.conn.execute('select brand_slug from change_summary(%s, p_exclude_brand_ids => %s)',
                                    ('2026-11-02', [self.acme['id']])).fetchall()
        self.assertEqual(summary, [])
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            titles(p_stock='maybe')

    def test_search_works_for_anon_in_a_fresh_session(self):
        # A new connection has not loaded pg_trgm yet, which is the situation on Supabase.
        with psycopg.connect(test_url(), autocommit=True) as fresh:
            with fresh.transaction():
                fresh.execute('set local role anon')
                titles = [row[0] for row in fresh.execute("select title from search_products(p_query => 'loafers')")]
                count = fresh.execute("select search_products_count(p_query => 'loafers')").fetchone()[0]
        self.assertEqual(titles, ['Leather Loafers'])
        self.assertEqual(count, 1)


class NonSuperuserMigrationTests(unittest.TestCase):
    """Supabase runs migrations as a role that is not a superuser. Apply every migration that way."""

    @unittest.skipUnless(ADMIN_URL, 'TEST_DATABASE_URL is not set')
    def test_migrations_apply_without_superuser(self):
        name = 'stockwatch_nosuper'
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(f'drop database if exists {name} with (force)')
            admin.execute('drop role if exists migrator')
            admin.execute("create role migrator login password 'migrator' createrole nosuperuser")
            admin.execute(f'create database {name} owner migrator')
        try:
            url = conninfo.make_conninfo(ADMIN_URL, dbname=name)
            with psycopg.connect(url, autocommit=True) as conn:
                # Superuser-only setup that Supabase provides before any migration runs.
                conn.execute(BOOTSTRAP.read_text(encoding='utf-8'))
                conn.execute('create extension pg_trgm with schema extensions')
                conn.execute('create extension vector with schema extensions')
                conn.execute('grant all on schema public, extensions, auth to migrator')
                conn.execute('grant references, trigger, select on auth.users to migrator')
                conn.execute('grant anon, authenticated, service_role to migrator')
            user_url = conninfo.make_conninfo(url, user='migrator', password='migrator',
                                              options='-c search_path=public,extensions')
            # One migration per session, like successive workflow runs: a session that has not
            # used pg_trgm yet has not loaded its library (that is what broke on 2026-11-17).
            while True:
                with psycopg.connect(user_url, autocommit=True) as conn:
                    self.assertFalse(conn.execute('select rolsuper from pg_roles where rolname = current_user').fetchone()[0])
                    todo = migrate.pending(conn)
                    if not todo:
                        break
                    version, label = todo[0].stem.split('_', 1)
                    with conn.transaction():
                        conn.execute(todo[0].read_text(encoding='utf-8'))
                        conn.execute('insert into supabase_migrations.schema_migrations (version, name) values (%s, %s)',
                                     (version, label))
            with psycopg.connect(user_url, autocommit=True) as conn:
                titles = conn.execute("select title from search_products(p_query => 'x')").fetchall()
                self.assertEqual(titles, [])
        finally:
            with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
                admin.execute(f'drop database if exists {name} with (force)')
                admin.execute('drop role if exists migrator')


class BrandTypesApiTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        self.shop = self.brand('shop')
        products = {}
        for i in range(4):
            products[f'f{i}'] = product(title=f'Flat {i}', type='Ladies Flats', tags=[])
        for i in range(3):
            products[f'h{i}'] = product(title=f'Heel {i}', type='Heels', tags=[])
        products['odd'] = product(title='Odd One', type='Rare', tags=[])
        products['none'] = product(title='Untyped', type=None, tags=[])
        ingest.ingest_snapshot(self.conn, self.shop, 'c1', snapshot(products), now=T0)

    def types(self, brand_id):
        return self.conn.execute('select raw_type, products from brand_types(%s::smallint)', (brand_id,)).fetchall()

    def test_brand_types_lists_common_types(self):
        self.assertEqual(self.types(self.shop['id']), [('Ladies Flats', 4), ('Heels', 3)])

    def test_brand_types_respects_the_switch(self):
        self.conn.execute("update brands set show_types = false where slug = 'shop'")
        self.assertEqual(self.types(self.shop['id']), [])

    def test_type_filter_in_search_and_count(self):
        args = {'b': [self.shop['id']], 't': ['Heels', 'Rare']}
        titles = self.conn.execute('select title from search_products(p_brand_ids => %(b)s, p_types => %(t)s, '
                                   "p_sort => 'price_asc')", args).fetchall()
        self.assertCountEqual([row[0] for row in titles], ['Heel 0', 'Heel 1', 'Heel 2', 'Odd One'])
        count = self.scalar('select search_products_count(p_brand_ids => %(b)s, p_types => %(t)s)', args)
        self.assertEqual(count, 4)
        self.assertEqual(self.scalar('select search_products_count(p_brand_ids => %(b)s)', args), 9)

if __name__ == '__main__':
    unittest.main()
