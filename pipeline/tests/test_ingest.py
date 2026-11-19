import json
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from pipeline import ingest
from pipeline.tests.support import DatabaseTest, T0, day, product, snapshot, variant


class IngestSnapshotTests(DatabaseTest):
    def load(self, brand, sha, products, at=T0, **kwargs):
        kwargs.setdefault('now', at)
        return ingest.ingest_snapshot(self.conn, brand, sha, snapshot(products, at=at), **kwargs)

    def test_first_scan_creates_rows_without_events_or_history(self):
        brand = self.brand()
        result = self.load(brand, 'c1', {
            'p1': product({'v1': variant(250000, compare_at=500000), 'v2': variant(300000, available=False, size='L')}),
            'p2': product({'v1': variant(100000, available=False)}),
        })
        self.assertEqual(result, 'ok')
        self.assertEqual(self.scalar('select count(*) from product_events'), 0)
        self.assertEqual(self.scalar('select count(*) from price_points'), 0)
        self.assertEqual(self.scalar('select count(*) from stock_points'), 0)
        row = self.conn.execute(
            """select available, price_min, price_max, compare_at_max, discount_pct, category, gender,
                      last_price_change_at, last_restock_at
               from products where external_id = 'p1'""").fetchone()
        self.assertEqual(row, (True, 250000, 300000, 500000, 50, 'eastern', 'women', None, None))
        self.assertFalse(self.scalar("select available from products where external_id = 'p2'"))
        self.assertEqual(self.scalar('select product_count from brands'), 2)
        self.assertEqual(self.scalar('select last_commit_sha from ingest_cursor'), 'c1')
        self.assertEqual(self.scalar("select size_norm from variants where external_id = 'v2'"), 'L')

    def test_same_commit_twice_is_skipped(self):
        brand = self.brand()
        products = {'p1': product()}
        self.load(brand, 'c1', products)
        self.assertEqual(self.load(brand, 'c1', products), 'skipped')
        self.assertEqual(self.scalar('select count(*) from scans'), 1)

    def test_unchanged_snapshot_under_a_new_commit_writes_nothing(self):
        brand = self.brand()
        products = {'p1': product(), 'p2': product({'v1': variant(), 'v2': variant(size='L')})}
        self.load(brand, 'c1', products)
        before = self.conn.execute('select xmin::text, id from products order by id').fetchall()
        self.load(brand, 'c2', products, at=day(1))
        self.assertEqual(self.scalar('select count(*) from product_events'), 0)
        self.assertEqual(self.scalar('select count(*) from price_points'), 0)
        self.assertEqual(self.scalar('select count(*) from variants'), 3)
        self.assertEqual(self.conn.execute('select xmin::text, id from products order by id').fetchall(), before)
        self.assertEqual(self.scalar("select change_count from scans where commit_sha = 'c2'"), 0)

    def test_price_drop_records_baseline_and_new_point(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product({'v1': variant(500000)})})
        self.load(brand, 'c2', {'p1': product({'v1': variant(400000)})}, at=day(1))
        self.assertEqual(self.events(), [('price_drop', 'p1')])
        points = self.conn.execute('select observed_at, price from price_points order by observed_at').fetchall()
        self.assertEqual(points, [(T0, 500000), (day(1), 400000)])
        old, new = self.conn.execute('select old_value, new_value from product_events').fetchone()
        self.assertEqual((old['price'], new['price']), (500000, 400000))
        self.assertEqual(self.scalar('select last_price_change_at from products'), day(1))
        self.load(brand, 'c3', {'p1': product({'v1': variant(450000)})}, at=day(2))
        self.assertEqual(self.events(), [('price_drop', 'p1'), ('price_rise', 'p1')])
        self.assertEqual(self.scalar('select count(*) from price_points'), 3)

    def test_sale_start_and_end(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product({'v1': variant(500000)})})
        self.load(brand, 'c2', {'p1': product({'v1': variant(350000, compare_at=500000)})}, at=day(1))
        self.assertEqual(self.events(), [('price_drop', 'p1'), ('sale_started', 'p1')])
        self.assertEqual(self.scalar('select discount_pct from products'), 30)
        self.load(brand, 'c3', {'p1': product({'v1': variant(500000)})}, at=day(2))
        self.assertEqual(self.events(), [('price_drop', 'p1'), ('price_rise', 'p1'), ('sale_ended', 'p1'),
                                         ('sale_started', 'p1')])
        self.assertEqual(self.scalar('select discount_pct from products'), 0)

    def test_one_size_restock_is_a_variant_event_only(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product({'v1': variant(), 'v2': variant(available=False, size='L')})})
        self.load(brand, 'c2', {'p1': product({'v1': variant(), 'v2': variant(size='L')})}, at=day(1))
        self.assertEqual(self.events('product'), [])
        self.assertEqual(self.events('variant'), [('back_in_stock', 'p1')])
        points = self.conn.execute('select observed_at, available from stock_points order by observed_at').fetchall()
        self.assertEqual(points, [(T0, False), (day(1), True)])

    def test_product_sells_out_and_returns(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product({'v1': variant()})})
        self.load(brand, 'c2', {'p1': product({'v1': variant(available=False)})}, at=day(1))
        self.assertEqual(self.events('all'), [('out_of_stock', 'p1')])
        self.assertIsNone(self.scalar('select last_restock_at from products'))
        self.load(brand, 'c3', {'p1': product({'v1': variant()})}, at=day(2))
        self.assertEqual(self.events('product'), [('back_in_stock', 'p1'), ('out_of_stock', 'p1')])
        self.assertEqual(self.events('variant'), [('back_in_stock', 'p1')])
        self.assertEqual(self.scalar('select last_restock_at from products'), day(2))
        self.assertEqual(self.scalar('select count(*) from stock_points'), 3)

    def test_out_of_stock_does_not_look_like_a_price_change(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product({'v1': variant(400000, available=False), 'v2': variant(500000, size='L')})})
        self.load(brand, 'c2', {'p1': product({'v1': variant(400000, available=False),
                                               'v2': variant(500000, available=False, size='L')})}, at=day(1))
        self.assertEqual(self.events(), [('out_of_stock', 'p1')])

    def test_new_product_and_new_variant(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product()})
        self.load(brand, 'c2', {'p1': product({'v1': variant(), 'v2': variant(size='L')}),
                                'p2': product({'v1': variant(), 'v2': variant(size='L')})}, at=day(1))
        self.assertEqual(self.events('product'), [('new_product', 'p2')])
        self.assertEqual(self.events('variant'), [('new_variant', 'p1')])
        self.assertEqual(self.scalar("select first_seen_at from products where external_id = 'p2'"), day(1))

    def test_removed_product_and_return(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product(), 'p2': product(), 'p3': product()})
        self.load(brand, 'c2', {'p1': product(), 'p2': product()}, at=day(1))
        self.assertEqual(self.events(), [('removed', 'p3')])
        self.assertEqual(self.scalar("select removed_at from products where external_id = 'p3'"), day(1))
        self.assertFalse(self.scalar("select notifiable from product_events where kind = 'removed'"))
        self.load(brand, 'c3', {'p1': product(), 'p2': product(), 'p3': product()}, at=day(2))
        self.assertIsNone(self.scalar("select removed_at from products where external_id = 'p3'"))
        self.assertEqual(self.events(), [('removed', 'p3')])
        self.assertEqual(self.scalar('select count(*) from products'), 3)

    def test_removed_variant_counts_as_unavailable(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product({'v1': variant(available=False), 'v2': variant(size='L')})})
        self.load(brand, 'c2', {'p1': product({'v1': variant(available=False)})}, at=day(1))
        self.assertEqual(self.events('all'), [('out_of_stock', 'p1')])
        self.assertEqual(self.scalar("select removed_at from variants where external_id = 'v2'"), day(1))
        points = self.conn.execute('select observed_at, available from stock_points order by observed_at').fetchall()
        self.assertEqual(points, [(T0, True), (day(1), False)])
        self.load(brand, 'c3', {'p1': product({'v1': variant(available=False), 'v2': variant(size='L')})}, at=day(2))
        self.assertIsNone(self.scalar("select removed_at from variants where external_id = 'v2'"))
        self.assertEqual(self.events('product'), [('back_in_stock', 'p1'), ('out_of_stock', 'p1')])

    def test_product_level_brand_has_no_variant_events(self):
        brand = self.brand('khaadi', granularity='product')
        self.load(brand, 'c1', {'p1': product({'p1': variant(available=False, size='Default')})})
        self.load(brand, 'c2', {'p1': product({'p1': variant(size='Default')})}, at=day(1))
        self.assertEqual(self.events('all'), [('back_in_stock', 'p1')])
        self.assertEqual(self.events('variant'), [])

    def test_metadata_change_updates_row_without_event(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product()})
        self.load(brand, 'c2', {'p1': product(title='Denim Jacket', type='Jackets', tags=['Men'])}, at=day(1))
        row = self.conn.execute('select title, category, gender from products').fetchone()
        self.assertEqual(row, ('Denim Jacket', 'western', 'men'))
        self.assertEqual(self.scalar('select count(*) from product_events'), 0)
        self.assertTrue(self.scalar("select search @@ to_tsquery('english', 'jacket & acme') from products"))

    def test_description_and_images_are_cleaned(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product(description='<p>Soft&nbsp;lawn</p>\n<b>x</b>' + 'y' * 5000,
                                              images=['//cdn.example/a.jpg'] + ['https://cdn.example/b.jpg'] * 20)})
        description, images = self.conn.execute('select description, images from products').fetchone()
        self.assertTrue(description.startswith('Soft lawn x'))
        self.assertEqual(len(description), 2000)
        self.assertEqual(images[0], 'https://cdn.example/a.jpg')
        self.assertEqual(len(images), 8)

    def test_old_snapshots_are_not_notifiable(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product({'v1': variant(500000)})})
        self.load(brand, 'c2', {'p1': product({'v1': variant(400000)})}, at=day(1), now=day(1) + timedelta(hours=30))
        self.load(brand, 'c3', {'p1': product({'v1': variant(300000)})}, at=day(2), now=day(2) + timedelta(hours=2))
        flags = self.conn.execute('select notifiable from product_events order by observed_at').fetchall()
        self.assertEqual(flags, [(False,), (True,)])

    def test_bad_snapshots_are_rejected_and_change_nothing(self):
        brand = self.brand()
        self.load(brand, 'c1', {f'p{i}': product() for i in range(10)})
        good = {f'p{i}': product() for i in range(10)}
        cases = {
            'schema': snapshot(good, schema_version=2),
            'currency': snapshot(good, currency='SAR'),
            'unit': snapshot(good, price_unit='major'),
            'empty': snapshot({}),
            'shrunk': snapshot({f'p{i}': product() for i in range(4)}),
            'rekeyed': snapshot({f'new{i}': product() for i in range(10)}),
            'price': snapshot({**good, 'p0': product({'v1': variant(price='1,999')})}),
        }
        for name, bad in cases.items():
            with self.subTest(name), self.assertRaises(ingest.Rejected):
                ingest.ingest_snapshot(self.conn, brand, f'bad-{name}', bad, now=T0)
        self.assertEqual(self.scalar('select count(*) from products where removed_at is null'), 10)
        self.assertEqual(self.scalar('select count(*) from product_events'), 0)
        self.assertEqual(self.scalar('select count(*) from scans'), 1)

    def test_force_accepts_a_shrunk_catalog(self):
        brand = self.brand()
        self.load(brand, 'c1', {f'p{i}': product() for i in range(10)})
        self.load(brand, 'c2', {f'p{i}': product() for i in range(4)}, at=day(1), force=True)
        self.assertEqual(self.scalar('select count(*) from products where removed_at is null'), 4)

    def test_exactly_half_remaining_is_accepted(self):
        brand = self.brand()
        self.load(brand, 'c1', {f'p{i}': product() for i in range(10)})
        self.load(brand, 'c2', {f'p{i}': product() for i in range(5)}, at=day(1))
        self.assertEqual(self.scalar('select count(*) from products where removed_at is null'), 5)

    def test_failure_inside_merge_rolls_everything_back(self):
        brand = self.brand()
        self.load(brand, 'c1', {'p1': product()})
        broken = dict(brand, name=None)  # brand name is only used late, inside the product update
        self.conn.execute('alter table products add constraint no_jackets check (title <> %s)' % "'Boom'")
        try:
            with self.assertRaises(Exception):
                ingest.ingest_snapshot(self.conn, broken, 'c2', snapshot({'p1': product(title='Boom'), 'p2': product()},
                                                                         at=day(1)), now=day(1))
        finally:
            self.conn.execute('alter table products drop constraint no_jackets')
        self.assertEqual(self.scalar('select count(*) from products'), 1)
        self.assertEqual(self.scalar('select count(*) from scans'), 1)
        self.assertEqual(self.scalar('select last_commit_sha from ingest_cursor'), 'c1')

    def test_brands_are_independent(self):
        one, two = self.brand('one'), self.brand('two')
        self.load(one, 'c1', {'p1': product()})
        self.load(two, 'c1', {'p1': product(), 'p2': product()})
        self.load(one, 'c2', {'p1': product({'v1': variant(available=False)})}, at=day(1))
        self.assertEqual(self.scalar('select count(*) from products where brand_id = %s and removed_at is null',
                                     (two['id'],)), 2)
        self.assertEqual(self.events(), [('out_of_stock', 'p1')])


class GitIngestTests(DatabaseTest):
    """ingest_brand against a real (temporary) git repository."""

    def commit(self, repo, slug, data, message):
        path = Path(repo) / 'brands' / slug / 'state.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')
        run = lambda *args: subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)
        run('add', '-A')
        run('-c', 'user.name=t', '-c', 'user.email=t@example.com', 'commit', '-q', '-m', message)

    def make_repo(self):
        repo = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(['git', 'worktree', 'prune'], cwd=repo, capture_output=True))
        subprocess.run(['git', 'init', '-q', '-b', 'state', repo], check=True, capture_output=True)
        return repo

    def test_backfill_then_incremental_then_noop(self):
        repo = self.make_repo()
        brand, other = self.brand('acme'), self.brand('other')
        self.commit(repo, 'acme', snapshot({'p1': product({'v1': variant(500000)})}, at=day(0)), 'one')
        self.commit(repo, 'other', snapshot({'x': product()}, at=day(0)), 'unrelated brand')
        self.commit(repo, 'acme', snapshot({'p1': product({'v1': variant(400000)})}, at=day(1)), 'two')
        counts = ingest.ingest_brand(self.conn, brand, 'state', cwd=repo, now=day(1))
        self.assertEqual(counts, {'ok': 2, 'skipped': 0, 'rejected': 0})
        self.assertEqual(self.events(), [('price_drop', 'p1')])
        self.assertEqual(self.scalar('select count(*) from scans'), 2)

        self.commit(repo, 'acme', snapshot({'p1': product({'v1': variant(300000)})}, at=day(2)), 'three')
        counts = ingest.ingest_brand(self.conn, brand, 'state', cwd=repo, now=day(2))
        self.assertEqual(counts['ok'], 1)
        self.assertEqual(self.scalar('select count(*) from price_points'), 3)

        counts = ingest.ingest_brand(self.conn, brand, 'state', cwd=repo, now=day(2))
        self.assertEqual(counts, {'ok': 0, 'skipped': 0, 'rejected': 0})
        self.assertEqual(self.scalar('select count(*) from products where brand_id = %s', (other['id'],)), 0)

    def test_rejected_commit_is_skipped_and_a_later_good_one_loads(self):
        repo = self.make_repo()
        brand = self.brand('acme')
        full = {f'p{i}': product() for i in range(10)}
        self.commit(repo, 'acme', snapshot(full, at=day(0)), 'good')
        self.commit(repo, 'acme', snapshot({'p0': product()}, at=day(1)), 'broken scrape')
        self.commit(repo, 'acme', snapshot({**full, 'p0': product({'v1': variant(available=False)})}, at=day(2)), 'good')
        counts = ingest.ingest_brand(self.conn, brand, 'state', cwd=repo, now=day(2))
        self.assertEqual(counts, {'ok': 2, 'skipped': 0, 'rejected': 1})
        self.assertEqual(self.scalar('select count(*) from products where removed_at is null'), 10)
        self.assertEqual(self.events(), [('out_of_stock', 'p0')])
        self.assertEqual(self.scalar("select count(*) from scans where status = 'rejected' and error like 'only 1 of 10%'"), 1)
        self.assertEqual(self.scalar('select rejected_since_success from brand_health'), 0)

    def test_rewritten_history_is_an_error(self):
        repo = self.make_repo()
        brand = self.brand('acme')
        self.commit(repo, 'acme', snapshot({'p1': product()}, at=day(0)), 'one')
        ingest.ingest_brand(self.conn, brand, 'state', cwd=repo, now=day(0))
        self.conn.execute("update ingest_cursor set last_commit_sha = '0123456789012345678901234567890123456789'")
        with self.assertRaises(RuntimeError):
            ingest.ingest_brand(self.conn, brand, 'state', cwd=repo, now=day(0))

    def test_sync_brands_keeps_operator_edits(self):
        configs = {'acme': {'name': 'Acme', 'origin': 'https://acme.example', 'strategy': 'shopify_json'},
                   'khaadi': {'name': 'Khaadi', 'origin': 'https://pk.khaadi.com', 'strategy': 'sfcc'},
                   'gone': {'name': 'Gone', 'website': 'https://gone.example', 'strategy': 'unavailable'}}
        ingest.sync_brands(self.conn, configs)
        rows = self.conn.execute('select slug, granularity, is_visible from brands order by slug').fetchall()
        self.assertEqual(rows, [('acme', 'variant', True), ('gone', 'variant', False), ('khaadi', 'product', True)])
        self.conn.execute("update brands set is_visible = false, scan_tier = 'hot' where slug = 'acme'")
        configs['acme']['name'] = 'Acme Co'
        ingest.sync_brands(self.conn, configs)
        row = self.conn.execute("select name, is_visible, scan_tier from brands where slug = 'acme'").fetchone()
        self.assertEqual(row, ('Acme Co', False, 'hot'))

    def test_only_selected_and_enabled_brands_are_loaded(self):
        for slug in ('acme', 'big', 'off'):
            self.brand(slug)
        self.conn.execute("update brands set ingest_enabled = false where slug = 'off'")
        slugs = [brand['slug'] for brand in ingest.enabled_brands(self.conn, [], ['acme', 'off'])]
        self.assertEqual(slugs, ['acme'])
        self.assertEqual(ingest.enabled_brands(self.conn, [], []), [])
        with self.assertRaises(SystemExit):
            ingest.enabled_brands(self.conn, ['big'], ['acme'])

    def test_drop_brand_removes_its_data_only(self):
        keep, gone = self.brand('acme'), self.brand('big')
        for brand in (keep, gone):
            ingest.ingest_snapshot(self.conn, brand, 'c1', snapshot({'p1': product({'v1': variant(500000)})}), now=T0)
            ingest.ingest_snapshot(self.conn, brand, 'c2', snapshot({'p1': product({'v1': variant(400000)})}, at=day(1)),
                                   now=day(1))
        self.assertEqual(ingest.drop_brand(self.conn, 'big'), 1)
        for table, expected in (('products', 1), ('variants', 1), ('price_points', 2), ('product_events', 1),
                                ('scans', 2), ('ingest_cursor', 1), ('brands', 2)):
            self.assertEqual(self.scalar(f'select count(*) from {table}'), expected, table)
        self.assertEqual(self.scalar("select product_count from brands where slug = 'big'"), 0)
        ingest.ingest_snapshot(self.conn, gone, 'c2', snapshot({'p1': product()}, at=day(1)), now=day(1))
        self.assertEqual(self.scalar('select count(*) from products'), 2)
        with self.assertRaises(SystemExit):
            ingest.drop_brand(self.conn, 'nope')

    def test_brands_load_in_the_owners_order(self):
        for slug in ('acme', 'big', 'zed'):
            self.brand(slug)
        slugs = [brand['slug'] for brand in ingest.enabled_brands(self.conn, [], ['zed', 'acme', 'big'])]
        self.assertEqual(slugs, ['zed', 'acme', 'big'])

    def test_a_full_database_stops_new_brands_but_not_loaded_ones(self):
        loaded, new = self.brand('acme'), self.brand('big')
        ingest.ingest_snapshot(self.conn, loaded, 'c1', snapshot({'p1': product()}), now=T0)
        self.assertTrue(ingest.has_room_for_new_brand(self.conn, new, max_mb=100000))
        self.assertFalse(ingest.has_room_for_new_brand(self.conn, new, max_mb=1))
        self.assertTrue(ingest.has_room_for_new_brand(self.conn, loaded, max_mb=1))

    def test_checked_in_selection_names_real_brands(self):
        configs = json.loads(ingest.SCRAPERS.read_text(encoding='utf-8'))
        self.assertTrue(set(ingest.included_slugs()) <= set(configs))


class BrandTypesTests(DatabaseTest):
    def test_checked_in_brand_types_are_valid(self):
        brand_types = ingest.load_brand_types()
        configs = json.loads(ingest.SCRAPERS.read_text(encoding='utf-8'))
        self.assertTrue(set(brand_types) <= set(configs))

    def test_bad_brand_types_fail_loudly(self):
        path = Path(tempfile.mkdtemp()) / 'brand_types.json'
        for bad in ({'acme': {'primary': 'shoes'}}, {'acme': {'types': {'X': 'nope'}}}, {'acme': {'shwo_types': False}}):
            path.write_text(json.dumps({'brands': bad}), encoding='utf-8')
            with self.subTest(bad), self.assertRaises(ValueError):
                ingest.load_brand_types(path)

    def test_brand_rules_apply_on_ingest(self):
        brand = self.brand('shoes')
        rules = {'shoes': {'primary': 'footwear', 'types': {'Bottle': 'bags-accessories'}}}
        ingest.ingest_snapshot(self.conn, brand, 'c1', snapshot({
            'a': product(title='Alden Stocks', type='MEN FORMAL', tags=[]),
            'b': product(title='Water Bottle', type='Bottle', tags=[]),
        }), now=T0, brand_types=rules)
        rows = self.conn.execute('select external_id, category from products order by 1').fetchall()
        self.assertEqual(rows, [('a', 'footwear'), ('b', 'bags-accessories')])

    def test_relabel_updates_only_changed_products_and_search(self):
        brand = self.brand('shoes')
        ingest.ingest_snapshot(self.conn, brand, 'c1', snapshot({
            'a': product(title='Alden Stocks', type='MEN FORMAL', tags=[]),
            'b': product(title='Leather Loafers', type='Shoes', tags=[]),
        }), now=T0)
        self.assertEqual(self.scalar("select category from products where external_id = 'a'"), 'formal')
        untouched = self.scalar("select xmin::text from products where external_id = 'b'")
        self.assertEqual(ingest.relabel(self.conn, {'shoes': {'primary': 'footwear'}}), 1)
        self.assertEqual(self.scalar("select category from products where external_id = 'a'"), 'footwear')
        self.assertTrue(self.scalar("select search @@ to_tsquery('english', 'footwear') from products "
                                    "where external_id = 'a'"))
        self.assertEqual(self.scalar("select xmin::text from products where external_id = 'b'"), untouched)
        self.assertEqual(ingest.relabel(self.conn, {'shoes': {'primary': 'footwear'}}), 0)

    def test_relabel_runs_once_per_rules_version(self):
        brand = self.brand('shoes')
        ingest.ingest_snapshot(self.conn, brand, 'c1', snapshot({'a': product(title='Alden', type='MEN FORMAL')}),
                               now=T0)
        rules = {'shoes': {'primary': 'footwear'}}
        self.assertEqual(ingest.relabel_if_rules_changed(self.conn, rules), 1)
        self.assertIsNone(ingest.relabel_if_rules_changed(self.conn, rules))
        self.conn.execute("update pipeline_meta set value = 'old'")
        self.assertEqual(ingest.relabel_if_rules_changed(self.conn, rules), 0)

    def test_apply_brand_settings(self):
        self.brand('acme')
        self.brand('codes')
        ingest.apply_brand_settings(self.conn, {'codes': {'show_types': False}})
        rows = self.conn.execute('select slug, show_types from brands order by slug').fetchall()
        self.assertEqual(rows, [('acme', True), ('codes', False)])
        ingest.apply_brand_settings(self.conn, {})
        self.assertTrue(self.scalar("select show_types from brands where slug = 'codes'"))

if __name__ == '__main__':
    unittest.main()
