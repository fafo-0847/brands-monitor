"""Scrape rounds and several days in the change log (20261122000002_change_rounds.sql)."""
from datetime import timedelta

from pipeline import ingest
from pipeline.tests.support import DatabaseTest, T0, day, product, snapshot, variant

# T0 is 2026-11-01 06:00 in Pakistan. Round A: T0 and T0 + 10 min (no run id, grouped by time).
# Round B: T0 + 5 h and T0 + 5 h 20 min. Run 7: one day later, tagged by the scrape workflow.
A1, A2 = T0, T0 + timedelta(minutes=10)
B1, B2 = T0 + timedelta(hours=5), T0 + timedelta(hours=5, minutes=20)
R7 = day(1)


class RoundTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        acme, zed = self.brand('acme'), self.brand('zed')
        self.load(acme, 'a1', A1, {'p': product({'v': variant(500000)})})
        self.load(zed, 'z1', A2, {'q': product({'v': variant(200000, available=False)})})
        self.load(acme, 'a2', B1, {'p': product({'v': variant(400000)})})                    # price drop
        self.load(zed, 'z2', B2, {'q': product({'v': variant(200000)})})                     # back in stock
        self.load(acme, 'a3', R7, {'p': product({'v': variant(450000)})}, run_id=7)         # price rise

    def load(self, brand, sha, at, products, run_id=None):
        ingest.ingest_snapshot(self.conn, brand, sha, snapshot(products, at=at), now=at, run_id=run_id)

    def rounds(self, days):
        return self.conn.execute('select round_id, started_at, ended_at, brands, changes from change_rounds(%s::date[])',
                                 (days,)).fetchall()

    def kinds(self, query, params=None):
        return sorted(row[0] for row in self.conn.execute(query, params).fetchall())

    def test_rounds_are_grouped_by_run_or_by_time(self):
        first_day = self.rounds(['2026-11-01'])
        self.assertEqual([(start, end, brands, changes) for _, start, end, brands, changes in first_day],
                         [(B1, B2, 2, 2), (A1, A2, 2, 0)])
        self.assertEqual(first_day[1][0], -int(A1.timestamp()))
        self.assertEqual(self.rounds(['2026-11-02']), [(7, R7, R7, 1, 1)])
        self.assertEqual(len(self.rounds(['2026-11-01', '2026-11-02'])), 3)

    def test_change_log_by_round_and_by_several_days(self):
        b = self.rounds(['2026-11-01'])[0][0]
        self.assertEqual(self.kinds('select kind from recent_changes(p_rounds => %s)', ([b],)),
                         ['back_in_stock', 'price_drop'])
        self.assertEqual(self.kinds('select kind from recent_changes(p_rounds => %s)', ([7],)), ['price_rise'])
        self.assertEqual(self.kinds("select kind from recent_changes(p_days => '{2026-11-01,2026-11-02}')"),
                         ['back_in_stock', 'price_drop', 'price_rise'])
        # Days and rounds combine: run 7 found nothing on the first day.
        self.assertEqual(self.kinds("select kind from recent_changes(p_days => '{2026-11-01}', p_rounds => %s)",
                                    ([7],)), [])
        self.assertEqual(self.kinds("select kind from change_summary(p_days => '{2026-11-02}')"), ['price_rise'])
        self.assertEqual(self.kinds('select kind from change_summary(p_rounds => %s)', ([b, 7],)),
                         ['back_in_stock', 'price_drop', 'price_rise'])
        # The single-day parameter that older app builds send still works.
        self.assertEqual(self.kinds("select kind from recent_changes(p_day => '2026-11-02')"), ['price_rise'])
        self.assertEqual(self.scalar("select change_price_stats(p_rounds => %s) ->> 'n'", ([7],)), '1')

    def test_products_filtered_by_rounds_and_days(self):
        b = self.rounds(['2026-11-01'])[0][0]
        count = lambda args, params=None: self.scalar(f'select search_products_count({args})', params)
        self.assertEqual(count('p_changed_rounds => %s', ([7],)), 1)
        self.assertEqual(count('p_changed_rounds => %s', ([b],)), 2)
        self.assertEqual(count("p_changed_days => '{2026-11-01}'"), 2)
        self.assertEqual(count("p_changed_days => '{2026-11-02}'"), 1)
        self.assertEqual(count("p_changed_days => '{2026-11-01,2026-11-02}', p_change_kinds => '{price_rise}'"), 1)
        self.assertEqual(count("p_changed_day => '2026-11-02'"), 1)
        titles = self.conn.execute(
            "select id from search_products(p_changed_rounds => %s, p_sort => 'newest')", ([b],)).fetchall()
        self.assertEqual(len(titles), 2)

    def test_run_id_is_read_from_the_commit_message(self):
        self.assertEqual(ingest._RUN_ID.search('Update acme catalog state (run 45000290193)').group(1), '45000290193')
        self.assertIsNone(ingest._RUN_ID.search('Update acme catalog state'))
        self.assertEqual(self.scalar("select run_id from scans where commit_sha = 'a3'"), 7)
