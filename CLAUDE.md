# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python monitor (`monitor.py`) that snapshots the public Shopify catalogs of two Pakistani stores (Khushposh, Outfitters), diffs each snapshot against the previous baseline, and emails changes (stock, price, variants, product fields) via Resend. It runs on GitHub Actions; state is persisted on a separate `monitor-state` git branch, not the default branch.

## Commands

Requires Python 3.11+ (CI uses 3.12).

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v                                   # all tests
python -m unittest tests.test_monitor.MonitorTests.test_pagination -v     # single test
python monitor.py --dry-run                                               # Khushposh preview, no email, baseline untouched
python monitor.py --store outfitters --dry-run
python monitor.py --dry-run --email-on-first-run                          # preview whole catalog as "New product"
```

Playwright is used only for `APIRequestContext` (HTTP), so `playwright install` (browser download) is not needed. Tests mock all network and email calls. There is no linter or build step configured.

Dry runs write `preview-state.json`, `preview-changes.json`, `preview-email.html` into `data/` (Khushposh) or `data/outfitters/`. Real runs need `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_TO`. Proxy via `MONITOR_PROXY` / `HTTPS_PROXY` (Playwright doesn't pick these up automatically, see `request_options()`).

## Architecture

Pipeline in `main()`: load baseline → `scan()` → `changes_between(old, new)` → `notify()` → write report, then state.

- **Stores** are `Store` dataclasses in the `STORES` dict; adding a store means adding an entry there plus a `monitor_cfg` entry in `brands/generate.py` OVERRIDES (CI runs it via the brands workflow).
- **Two scan paths exist.** `scan()` currently routes both stores through `scan_collection_batch()`, which pages the collection's `/products.json?limit=250` endpoint and converts decimal string prices to integer minor units. The older path (`catalog_handles()` + `parse_collection()` HTML scraping + per-product `/products/<handle>.js` + membership re-check) is still in the file and is what the pagination tests exercise, but is unreachable for the two configured stores. The README describes the older path.
- **State shape** (`SCHEMA = 1`): products keyed by Shopify product ID, variants keyed by variant ID; prices are integer minor units (`199900` = PKR 1,999.00). `main()` rejects a baseline whose `schema_version` or `source` doesn't match.
- **Currency guard**: a `localization=PK` cookie is set and `/cart.js` must report `PKR` before any comparison.

## Invariants to preserve

- **Fail rather than overwrite the baseline.** Any HTTP error, malformed product, empty/duplicate catalog, pagination anomaly or currency mismatch must raise. `get()` raises `ValueError` immediately for non-retryable HTTP errors and retries only 429/5xx/transport errors.
- **State advances only after every email is accepted.** In `main()`, `notify()` runs before `atomic_json(report)` / `atomic_json(state)`; `test_email_failure_does_not_advance_state` guards this.
- **Idempotency keys must stay stable across retries**: key = store name + `fingerprint([event_key, payload])`, where `event_key` derives from the old baseline and new products. Emails are chunked at 60 changes. Don't add non-deterministic content (timestamps etc.) to the payload.
- All product text in emails goes through `html.escape`.

## CI / persistence (`.github/workflows/brands.yml`)

`monitor.yml` was removed: Khushposh and Outfitters run inside the brands workflow (strategy `monitor_store`, which calls `monitor.scan` unchanged; emails via `brands/mailer.py`). State lives at `brands/<slug>/` on `monitor-state`; on first run the restore step falls back to the old location (`state.json` / `outfitters/state.json`, via `python -m brands.run --legacy-state SLUG`). A `changes.json` without a `state.json` fails the job deliberately. Running `monitor.py` directly still works locally.

## Brand scrapers (`brands/`)

Separate from `monitor.py` (which must stay unchanged). `brands/probe.py` → `brands/registry.json` → `brands/generate.py` writes `brands/scrapers/<slug>.py` + `brands/scrapers.json` (edit `OVERRIDES`/`UNAVAILABLE` in `generate.py`, not generated modules). `brands/engine.py` holds the strategies (`shopify_json`, `shopify_handles`, `sfcc`, `sitemap_jsonld`) and emits monitor.py-compatible snapshots (`monitor_store` delegates to monitor.py for Khushposh/Outfitters); `brands/run.py` reuses `monitor.changes_between`/`notify`. CI: `.github/workflows/brands.yml`, state under `brands/<slug>/` on `monitor-state`. Shopify rate-limits `products.json` per IP across stores (429, multi-minute bans) — don't burst many brands locally. See `brands/README.md`.

## App database pipeline (`pipeline/`, `supabase/`)

Loads `monitor-state` snapshots into the Postgres database the mobile app reads (product spec: `PRD.md`; details: `pipeline/README.md`). It only reads the branch; the scraper does not depend on it. `pipeline/ingest.py` treats each commit touching `brands/<slug>/state.json` as one scan, loaded in one transaction and keyed by brand + commit SHA, so re-running is a no-op and the backfill and daily run share one code path. Schema and RLS live in `supabase/migrations/` (applied by `python -m pipeline.migrate`). CI: `ingest.yml` (after the brands workflow; needs the `DATABASE_URL` secret, does nothing without it) and `pipeline-tests.yml`.

```bash
pip install -r pipeline/requirements.txt
docker run -d --name stockwatch-pg -e POSTGRES_PASSWORD=postgres -p 54329:5432 pgvector/pgvector:pg17
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54329/postgres python -m unittest discover -s pipeline/tests -t . -v
```

Use `127.0.0.1`, not `localhost` (IPv6 lookup stalls on Windows). Pipeline tests are skipped when `TEST_DATABASE_URL` is unset. Rules to keep: never rewrite unchanged rows (the catalog is ~376k products / ~1.4M variants and is re-read daily); history points are written only on change; a brand's first scan emits no events; snapshots sharing under half of the live products are rejected unless `--force`. Only brands the owner lists in `pipeline/ingest_brands.json` are loaded; do not edit that selection yourself. Keep `DEV_NOTES.md` (assumptions, known data problems, open items) up to date as you work.
