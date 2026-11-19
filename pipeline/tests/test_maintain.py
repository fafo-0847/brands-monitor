"""pipeline/maintain.py: trimming matches what ingest stores, retention, and guarded compaction."""
import unittest
from datetime import datetime, timedelta, timezone

from pipeline import ingest, maintain, normalize
from pipeline.tests.support import DatabaseTest, T0, day, product, snapshot, variant

QUIET = lambda message: None  # noqa: E731

RAW_IMAGES = ['//cdn.example/a.jpg?v=1', 'https://cdn.example/b.jpg?v=2&width=400',
              'https://cdn.example/c.jpg?width=400&v=3', 'https://cdn.example/d.jpg', 'https://cdn.example/e.jpg']


class MaintainTests(DatabaseTest):
    def test_sql_image_rule_matches_python(self):
        urls = ['https://x/a.jpg?v=1792829380', 'https://x/a.jpg?v=1&width=400', 'https://x/a.jpg?width=400&v=1',
                'https://x/a.jpg?w=1&v=2&h=3', 'https://x/a.jpg?version=2', 'https://x/a.jpg', 'https://x/a.jpg?v=1&v=2']
        for url in urls:
            with self.subTest(url):
                self.assertEqual(self.scalar('select private.clean_image_url(%s)', (url,)), normalize.clean_image_url(url))

    def test_trimmed_rows_match_ingest_and_are_not_rewritten_again(self):
        brand = self.brand()
        raw = {'p1': product(description='word ' * 400, images=RAW_IMAGES)}
        ingest.ingest_snapshot(self.conn, brand, 'c1', snapshot(raw), now=T0)
        expected = self.conn.execute('select images, description from products').fetchone()
        # Make the row look like one stored before the limits existed.
        self.conn.execute("""update products set images = %s, description = %s,
                             options = '[{"name": "Size", "values": ["M"]}]'""",
                          (['https://cdn.example/a.jpg?v=1'] + RAW_IMAGES[1:] + ['https://cdn.example/f.jpg'] * 3,
                           ('word ' * 400).strip()))
        self.assertEqual(maintain.trim_products(self.conn, log=QUIET), 1)
        self.assertEqual(self.conn.execute('select images, description from products').fetchone(), expected)
        self.assertIsNone(self.scalar('select options from products'))
        self.assertEqual(maintain.trim_products(self.conn, log=QUIET), 0)
        before = self.scalar('select xmin::text from products')
        ingest.ingest_snapshot(self.conn, brand, 'c2', snapshot(raw, at=day(1)), now=day(1))
        self.assertEqual(self.scalar('select xmin::text from products'), before)

    def test_retention(self):
        brand = self.brand()
        ingest.ingest_snapshot(self.conn, brand, 'c1', snapshot({'p1': product({'v1': variant(500000)}),
                                                                 'p2': product(), 'p3': product()}), now=T0)
        ingest.ingest_snapshot(self.conn, brand, 'c2', snapshot({'p1': product({'v1': variant(400000)}),
                                                                 'p2': product()}, at=day(1)), now=day(1))
        now = datetime.now(timezone.utc)
        self.conn.execute("update product_events set observed_at = %s where kind = 'price_drop'", (now - timedelta(days=91),))
        self.conn.execute("update products set removed_at = %s where external_id = 'p3'", (now - timedelta(days=61),))
        events, removed = maintain.apply_retention(self.conn, log=QUIET)
        self.assertEqual((events, removed), (1, 1))
        self.assertEqual(self.scalar('select count(*) from products'), 2)
        self.assertEqual(self.scalar('select count(*) from price_points'), 2)  # price history is kept
        self.assertEqual(maintain.apply_retention(self.conn, log=QUIET), (0, 0))

    def test_compact_respects_the_ceiling(self):
        brand = self.brand()
        ingest.ingest_snapshot(self.conn, brand, 'c1', snapshot({'p1': product()}), now=T0)
        rebuilt, skipped = maintain.compact(self.conn, ceiling_mb=1, log=QUIET)
        self.assertEqual(rebuilt, [])
        self.assertIn('products', skipped)
        rebuilt, skipped = maintain.compact(self.conn, ceiling_mb=100000, log=QUIET)
        self.assertIn('products', rebuilt)
        self.assertEqual(skipped, [])
        self.assertEqual(self.scalar('select count(*) from products'), 1)


if __name__ == '__main__':
    unittest.main()
