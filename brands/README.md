# Brand scrapers

One scraper per brand in `Pakistan Fashion Brands - Brands.csv`, sitting beside the original
Khushposh/Outfitters monitor (`monitor.py`, unchanged). Snapshots use the same state shape as
`monitor.py`, so `monitor.changes_between()` diffs them.

## Pipeline

1. `python brands/probe.py [--start N --end M | --only slug ...]` — per brand: saves raw HTML to
   `raw_html/<slug>/` (homepage, `collections_all.html` / `listing.html`, first `products_page1.json`,
   sitemap URL lists), detects the platform and finds the all-products URL. Results go to
   `brands/registry.json`; progress to `logs/probe.log`.
2. `python brands/generate.py` — writes `brands/scrapers/<slug>.py` (one module per brand, holding its
   `CONFIG`) and `brands/scrapers.json` from the registry plus the manual `OVERRIDES` / `UNAVAILABLE`
   tables in `generate.py`. Edit those tables, not the generated modules.
3. `python -m brands.run --brand <slug> [...]` or `--all` — scrapes one brand at a time, writes
   `data/brands/<slug>/state.json` + `changes.json`. `--limit N` is a smoke test (writes only
   `preview-*.json`, never the baseline). Progress to `logs/brands.log`, summary to
   `logs/brands-summary.json`.

## Strategies (`brands/engine.py`)

| Strategy | Used for | All-products source |
| --- | --- | --- |
| `shopify_json` | Most brands (Shopify) | `<origin>/collections/all/products.json?limit=250&page=N` |
| `shopify_handles` | Shopify stores with an empty products.json (Republic) | sitemap handles → `/products/<handle>.js` |
| `sfcc` | Khaadi, Sapphire (Salesforce Commerce Cloud) | No all-products page: top-level category URLs paged with `start`/`sz`, deduped by product ID; product-level only (no sizes) |
| `hydrogen_listing` | Breakout, Equator, Orient (Shopify Hydrogen) | Decodes the turbo-stream data on `/collections/all` pages (cursor or `?page=N`). Listing "available" is trusted; products whose first size is sold out are confirmed on their product page; sitemap products missing from the listing are read individually |
| `bareeze_listing` | Bareeze (Next.js) | Every top-level category from its category sitemap; one extra request per category fetches the cumulative "load more" last page; deduped by product ID |
| `sitemap_jsonld` | Cougar (Hydrogen listing has no stock data), Mango | Product sitemap → each product page's JSON-LD |
| `unavailable` | Charizma (DNS), Mushq (423), Metro (402), Kayseria/Leisure Club (no published products), ECS, Image | — |

## Rate limits

Shopify rate-limits `products.json` per IP across all Shopify stores (HTTP 429, `Retry-After: 60`).
Bursting through many stores quickly triggers bans of several minutes. Run with
`--pause 2 --between 20` (or slower) when scanning many brands in one go.

## GitHub Actions (`.github/workflows/brands.yml`)

Same pattern as `monitor.yml`: a `plan` job builds the matrix from `python -m brands.run --matrix`
(every brand except `unavailable` ones and `outfitters`, which `monitor.yml` already covers), then one
job per brand runs with `max-parallel: 1` and `fail-fast: false`. Each job restores
`brands/<slug>/state.json` from the `monitor-state` branch, runs
`python -m brands.run --brand <slug> --state data/state.json --report data/changes.json`, emails changes
through Resend (same `RESEND_API_KEY` / `EMAIL_FROM` / `EMAIL_TO` secrets) and commits the new state and
report back to `monitor-state/brands/<slug>/`. The first run per brand only creates the baseline.
The baseline advances only after Resend accepts every email. Emails go through `brands/mailer.py`: one email per brand run, split only if the payload would exceed 10 MB (about 20,000 changes at ~500 bytes each).

Runs daily at 01:07 UTC (`cron` in `brands.yml`), or manually via **Actions → Monitor Pakistan fashion
brands → Run workflow**, optionally with space-separated slugs to run only some brands. It uses its own
concurrency group so it never delays `monitor.yml`; its push step retries on top of the latest
`monitor-state` if both workflows push at the same time.

## Known CI behaviour

- A baseline saved by an older strategy for the same site (different `source`) is replaced without email on the next run; a baseline from another site fails the job.
- 429/5xx: up to 6 attempts, honouring `Retry-After` (capped at 120s). Republic is paced at 1 request/s (`min_pause`).
- HTTP 403 means the site blocks the runner's IP (seen on Equator from GitHub Actions); set a `MONITOR_PROXY` secret/env to route through a proxy.
- Lama Retail labels its rupee prices as SAR (`pkr_labelled_as`). Mango is excluded from Actions (429 on the first request from datacenter IPs).
- Khushposh and Outfitters run in this workflow too (`monitor_store` strategy → `monitor.scan`, unchanged). The old `monitor.yml` is removed so they are not checked or emailed twice.
