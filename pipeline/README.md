# Pipeline: snapshots → Postgres

Loads the scraper's snapshots (the `monitor-state` branch) into the Postgres database the app reads.
The scraper itself (`monitor.py`, `brands/`) is untouched and does not know this exists. See `PRD.md`
sections 5 and 7 for the design.

## Files

| Path | Purpose |
| --- | --- |
| `supabase/migrations/*.sql` | Schema, indexes, row-level security |
| `pipeline/migrate.py` | Applies pending migrations (same bookkeeping table as the Supabase CLI) |
| `pipeline/ingest.py` | Reads new commits per brand, upserts rows, writes history points and events |
| `pipeline/normalize.py` | Shared category / gender / size vocabulary, text cleaning |
| `pipeline/tests/` | Tests against a real Postgres |
| `.github/workflows/ingest.yml` | Runs after the brands workflow finishes, or manually |
| `.github/workflows/pipeline-tests.yml` | Runs the tests on changes to `pipeline/` or `supabase/` |

## Commands

```bash
pip install -r pipeline/requirements.txt

# A disposable local database (also what the tests use)
docker run -d --name stockwatch-pg -e POSTGRES_PASSWORD=postgres -p 54329:5432 pgvector/pgvector:pg17

# Tests. Use 127.0.0.1, not localhost: on Windows localhost tries IPv6 first and stalls.
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54329/postgres \
  python -m unittest discover -s pipeline/tests -t . -v

# Load into a database
export DATABASE_URL=postgresql://...
python -m pipeline.migrate
git fetch origin monitor-state
python -m pipeline.ingest                    # all enabled brands, only commits not loaded yet
python -m pipeline.ingest --brand khaadi     # some brands
python -m pipeline.ingest --stats            # table sizes
```

A plain local Postgres needs `pipeline/tests/local_supabase.sql` applied once before the migrations
(it creates the roles, `auth.users` and `auth.uid()` that Supabase provides). Supabase needs nothing extra.

## How a snapshot is loaded

One commit on `monitor-state` that touched `brands/<slug>/state.json` is one scan. For each, in one
transaction:

1. Validate (`schema_version` 1, PKR, minor units, integer prices, non-empty).
2. `COPY` products and variants into temporary staging tables.
3. Reject if fewer than half of the brand's live products are in the snapshot (broken scrape or a
   re-keyed catalog). `--force` overrides.
4. Merge with SQL: insert new rows, update changed ones, mark missing ones `removed_at`.
5. Write `price_points` / `stock_points` only for values that changed. The first change of a variant also
   writes the value it had since `first_seen_at`, so a variant with no points has never changed.
6. Recompute product-level numbers (`available`, `price_min`, `discount_pct`, …) for touched products and
   write `product_events`.
7. Record the scan and move the brand's cursor.

Rows that did not change are not rewritten, so a quiet day costs almost nothing.

### Events

Product-level events (`variant_id` is null) are what feeds and product watches use: `new_product`, `removed`,
`back_in_stock`, `out_of_stock`, `price_drop`, `price_rise`, `sale_started`, `sale_ended`. Price events
follow `price_min`, the lowest price over all listed variants whether in stock or not, so a size selling out
is never reported as a price change.

Variant-level events exist only for `back_in_stock` and `new_variant`, and only for brands whose
`granularity` is `variant`. Per-variant price history lives in `price_points`.

The first snapshot of a brand produces no events. Events from snapshots older than 24 hours are stored
with `notifiable = false`, so a backfill never notifies anyone.

### Rejected snapshots

A rejected snapshot is recorded in `scans` (`status = 'rejected'`, with the reason) and skipped; the
cursor moves past it so the next good scan repairs the brand. If a catalog really did shrink by more
than half, every later snapshot is rejected too: check `brand_health`, then run
`python -m pipeline.ingest --brand <slug> --force` (or the workflow with `force = yes`) on the next commit.

## GitHub Actions setup

Add a repository secret `DATABASE_URL`. For Supabase use the **session pooler** connection string
(Project → Connect → Session pooler); the direct connection is IPv6-only and GitHub runners have no IPv6.
Without the secret the workflow exits with a notice and does nothing.

Only brands listed under `include` in `pipeline/ingest_brands.json` are loaded (the owner's selection; the free
database cannot hold every brand). The optional repository variable `INGEST_BRANDS` narrows a single run
further, and `brands.ingest_enabled = false` switches one brand off.
