# Khushposh and Outfitters stock and price monitor

Python, Playwright, GitHub Actions and Resend for two collections.

- [Khushposh All Products](https://www.khushposh.co/collections/all)
- [Outfitters Men View All](https://outfitters.com.pk/collections/men-view-all-collection)

## What it tracks

- Each article by its stable Shopify **product ID**, rather than title or position.
- Each size/option combination by its stable **variant ID**.
- New and removed articles, sizes added/removed, restocks and sold-out sizes.
- Variant price increases/decreases and compare-at (original/strikethrough) price changes.
- Product titles, URLs/handles, descriptions, images, tags, vendor, type and options, plus variant SKU/option changes.
- PKR prices, stored as integer minor units: `199900` means **PKR 1,999.00**.

Playwright reads collection pages and the public `/products/<handle>.js` endpoint for each article. It follows Khushposh's numbered or Load More pagination and Outfitters' Ajaxinate links. Outfitters variants include color, size and season where present.

## GitHub setup

1. Copy the **contents** of this folder into your existing repository root, including `.github/workflows/monitor.yml`. Keep the workflow on the default branch and retain the existing `monitor-state` branch.
2. In Resend, create an API key and configure an allowed sender. For a custom sender, verify its domain in Resend. The testing sender `onboarding@resend.dev` is restricted to your own Resend account email; use it only under those testing restrictions.
3. Go to **GitHub repository → Settings → Secrets and variables → Actions → New repository secret** and add:

   | Secret | Example / meaning |
   | --- | --- |
   | `RESEND_API_KEY` | Your `re_...` Resend API key |
   | `EMAIL_FROM` | `Khushposh Monitor <alerts@your-verified-domain.com>` |
   | `EMAIL_TO` | Your recipient address; comma-separated addresses also work |

4. Ensure Actions are enabled and repository/organization policy allows the workflow's `contents: write` permission. The `monitor-state` branch must allow the Actions bot to create/update it; do not apply rules that block its direct commits.
5. Go to **Actions → Monitor Khushposh and Outfitters → Run workflow**. Each store creates its baseline on its first successful run. An existing Khushposh baseline carries forward.
6. Later runs email only changes. No changes means no email. Check the workflow logs for scan/email failures, and enable GitHub workflow-failure notifications if desired.

The workflow runs at `17` and `47` minutes past every UTC hour (every 30 minutes). In Pakistan that is also `:17` and `:47` each hour. Edit the cron expression in `monitor.yml` to change this. Scheduled runs can be delayed and are not exact timers. GitHub can disable schedules in inactive public repositories after 60 days.

Both stores use the **`monitor-state` branch** with separate files.

| Store | Baseline | Latest report |
| --- | --- | --- |
| Khushposh | `state.json` | `changes.json` |
| Outfitters | `outfitters/state.json` | `outfitters/changes.json` |

Every successful run replaces that store's snapshot and report. The next run compares against the latest committed snapshot. If Resend is needed, the workflow advances the state after Resend accepts the email. The stores run one at a time to avoid competing pushes, and either store can finish if the other fails. Git history retains the previous snapshots and reports.

## Local use

Requires Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python monitor.py --dry-run
python monitor.py --store outfitters --dry-run
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead of `source`.

`--dry-run` writes preview JSON and HTML in `data/` for Khushposh and `data/outfitters/` for Outfitters. This mode previews changes before sending email or saving a baseline. With no baseline, the change list is empty unless you also pass `--email-on-first-run`. To preview the initial catalog as new articles:

```bash
python monitor.py --dry-run --email-on-first-run
```

For real email runs, set `RESEND_API_KEY`, `EMAIL_FROM` and `EMAIL_TO` in your shell, then run:

```bash
python monitor.py
python monitor.py --store outfitters
```

The first real run saves the baseline with no initial email. Khushposh writes `data/state.json` and Outfitters writes `data/outfitters/state.json`. Use `python monitor.py --email-on-first-run` if you want an email listing all articles on that first run. To enable this behavior on GitHub, add the flag to the workflow's `python monitor.py` line **before the first run**.

Other flags: `--state PATH`, `--report PATH`, `--pause 0.35` (seconds between storefront requests). Do not run concurrent local processes against the same state file. GitHub workflow runs are serialized automatically. Optional proxy environments are supported through `MONITOR_PROXY` or `HTTPS_PROXY`.

## Email format

Each store sends its own email with an HTML table and a plain text version.

| Article (clickable) | Change | Details |
| --- | --- | --- |
| Example jeans | Back in stock | 32 |
| Example tee | Price decreased | M: PKR 1,999.00 → PKR 1,799.00 |
| Example jacket | New product | Price: PKR 3,999.00; available sizes/options: S, M, L |

Size/price rows link directly to the affected variant. Large reports are split into batches of 60 changes. Product text is HTML-escaped before insertion.

## Failure handling and practical limits

- HTTP errors, invalid/missing product data, absent grids, repeated pagination, inconsistent totals and currency mismatches fail the scan rather than overwrite your baseline.
- Both stores recheck collection membership after reading products. Khushposh also verifies the storefront total. Outfitters has no visible total in the supplied markup, so it follows consecutive Ajaxinate pages until the last page and checks for missing product links or duplicate articles across pages.
- The Pakistani localization cookie is set and `/cart.js` must report PKR before prices are compared.
- State advances only after all required emails are accepted by Resend. API acceptance does not guarantee inbox delivery; inspect Resend delivery logs for bounces.
- Resend idempotency keys reduce duplicate sends after failed requests or Git pushes. They expire after 24 hours. A changing catalog between partial email retries can still produce overlapping alerts; delivery and a Git commit are not one atomic transaction.
- These are periodic observations of the **public storefront**, not a stock database or a continuous event log. A size that sells out and restocks between runs can go unnoticed. Exact inventory counts are not exposed here. Each scan reads articles sequentially, so it is not a transactionally consistent snapshot of every product at one instant.
- Shopify buyability (`available`) is tracked: products allowed to sell on backorder can remain available. A removed article means absent from this collection, not confirmed deleted from the store.
- Only the fields listed above are tracked. Reviews, CSS/theme changes, delivery estimates, automatic checkout discounts and private inventory changes are outside this monitor.
- Persistent network/email failures leave the baseline unchanged; fix the reported error and rerun. A failed Git push after successful email can cause a retry; the stable idempotency key covers unchanged retry batches within the provider's 24-hour window.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests cover article/variant additions and removals, both price directions, stock transitions, HTML escaping, pagination completeness, invalid prices, stable email retry keys and keeping the baseline when email fails. They use fake email requests and send no messages.

## References

- [Shopify public product JSON API](https://shopify.dev/docs/api/ajax/reference/product)
- [Playwright APIRequestContext](https://playwright.dev/python/docs/api/class-apirequestcontext)
- [Resend send email](https://resend.com/docs/api-reference/emails/send-email)
- [Resend idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys)
- [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
