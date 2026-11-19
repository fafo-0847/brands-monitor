# PRD: Pakistan Fashion Price & Stock Tracker (working name "StockWatch PK")

Version 1.0, 2026-11-16. Owner: repo owner. Audience: coding agents and the owner.

All prices in this document are estimates in USD from public list prices as of the writing date. Verify each one on the vendor's pricing page before committing money.

---

## 1. Summary

A mobile app (Android first, iOS next, website in phase 2) where shoppers in Pakistan follow fashion brands and individual articles, see a price and stock history chart for every article, and get a push notification when something they follow comes back in stock, drops or rises in price, or when a followed brand adds new articles.

The data comes from the existing scraper in this repository. It already snapshots about 90 brand catalogs once a day on GitHub Actions and stores the latest state as JSON on the `monitor-state` git branch. The app replaces the current email digests, which are too noisy to read.

### Decisions already made by the owner

| Topic | Decision |
| --- | --- |
| Audience and revenue | Public app, free. Revenue later from affiliate/outbound links and optional ads |
| Scan freshness | Tiered: popular ("hot") brands every 1 to 2 hours, all others daily |
| Budget, first 6 months | USD 0 to 25 per month |
| Sign-in | Guest mode, Google sign-in, email (magic link or password) |
| Mobile stack | Expo (React Native) with TypeScript |
| Website / SEO | Phase 2. API and URLs are designed now so the site needs no rework |
| Backend | Supabase (Postgres, Auth, row-level security). Plain Postgres so it can move to AWS later |
| Search in v1 | Keyword search, filters and sorting. Semantic search is phase 2 |
| Things a user can follow | A product, a specific size/variant, a whole brand |
| Alert channels in v1 | Push notifications and an in-app inbox |
| Price history | Backfill from the git history of `monitor-state`, then record every scan |
| Language and theme | English, light and dark themes, built so Urdu (right-to-left) can be added later |

### Decisions added after the first review

| Topic | Decision |
| --- | --- |
| First release | **Private test build for the owner only** (an APK installed directly on the owner's phone). No Play Store work until the owner says so. M7 is on hold |
| Name, package ID, domain | Not decided. Use the placeholders below until the owner decides; they are free to change until the first Play Store upload |
| Scan frequency | Daily for all brands. No proxy, no hot tier yet. M6's hourly workflow is deferred; the `scan_tier` column stays so it can be switched on later |
| Owner email digests | Turn off, as part of M1, once ingest is verified (see M1) |
| Repository | Private now, public later |
| Affiliate links | None yet. Outbound links carry UTM parameters only |
| Categories | Use the proposed list in section 16 as the default; the owner can change it later without an app release |
| Play developer account | Not created. Decide before M7 |

Placeholders: app name `StockWatch PK`, Android package ID `com.stockwatchpk.app.dev`, no domain (share links use the Expo development scheme `stockwatch://`). All three live in one config file (`app.config.ts`) so they can be changed in one place.

### Not in v1

Website, semantic search, image search, target-price alerts, saved-search alerts, email digests to users, WhatsApp alerts, Urdu, iOS store release, payments, user reviews, in-app checkout.

---

## 2. Current system (what exists today)

Agents must read `CLAUDE.md` and `brands/README.md` before touching anything.

- `monitor.py`: original single-file monitor for Khushposh and Outfitters. **Must stay unchanged.**
- `brands/`: registry, generated per-brand configs, scraping strategies (`shopify_json`, `shopify_handles`, `sfcc`, `hydrogen_listing`, `bareeze_listing`, `sitemap_jsonld`, `monitor_store`), runner and mailer.
- `.github/workflows/brands.yml`: daily cron (`7 1 * * *`), one job per brand, `max-parallel: 1`. Each job restores `brands/<slug>/state.json` from `monitor-state`, scans, emails changes through Resend, then commits `state.json` and `changes.json` back to `monitor-state`.
- About 98 brands are configured, 7 are marked `unavailable`, and Mango is excluded from CI.

### Snapshot shape (`state.json`, `schema_version: 1`)

```json
{
  "schema_version": 1,
  "source": "https://example.pk/collections/all/products.json",
  "currency": "PKR",
  "price_unit": "minor_units",
  "checked_at": "2026-11-11T16:25:15+00:00",
  "products": {
    "<product_id>": {
      "id": "...", "title": "...", "handle": "...", "url": "...",
      "vendor": null, "type": null, "description": "...",
      "tags": [], "images": ["https://cdn..."], "options": null,
      "available": true,
      "variants": {
        "<variant_id>": {
          "id": "...", "title": "...", "options": ["M"], "sku": "...",
          "available": true, "price": 1499900, "compare_at_price": null
        }
      }
    }
  }
}
```

Prices are integers in minor units (`1499900` = PKR 14,999.00).

### Facts that shape the design

1. **Catalog size (measured 2026-11-16).** 85 brands have snapshots on `monitor-state`: 376,211 products and 1,375,150 variants, 1.19 GB of JSON. The branch holds 206 commits covering 2026-11-11 to 2026-11-16, so that is all the history available to backfill. Loaded into Postgres with full history this is **1.31 GB** (products 883 MB, variants 361 MB, history and events 53 MB).
   - Three brands (Khazanay, Stylo, Bachaa Party) have exactly 25,000 products, which is the `max_pages=100` × 250 limit in `strategy_shopify_json`. Their catalogs are cut off, and which 25,000 products are returned can differ between scans, producing false "new" and "removed" events. This needs a scraper fix before those brands are shown to users.
   - Cougar's 2026-11-16 snapshot has 866 products against 2,346 the day before (a partial scrape that the scraper accepted and emailed as 2,460 changes). The ingest rejected it.
2. **Size-level data is missing for some brands.** Khaadi and Sapphire (`sfcc`), Bareeze, Cougar and the Hydrogen stores (Breakout, Equator, Orient) are scraped at product level, with one pseudo-variant per product. Size alerts cannot work for these brands until their scrapers are extended.
3. **Images are remote URLs** on each brand's CDN. Some strategies keep only the first image.
4. **Categories are not normalized.** `type` and `tags` are whatever each brand uses, and are often null.
5. **Rate limits are the real constraint.** Shopify rate-limits `products.json` per IP across all Shopify stores (HTTP 429, bans of several minutes). Some sites block datacenter IPs outright (Equator returns 403 from GitHub Actions; Mango returns 429 on the first request).
6. **No history is stored** except in the commit history of `monitor-state`.

### Invariants that must survive this project

- A failed or suspicious scan never overwrites a baseline.
- `monitor.py` is not edited.
- Generated modules in `brands/scrapers/` are not edited by hand; edit `OVERRIDES` / `UNAVAILABLE` in `brands/generate.py`.
- The existing test suite keeps passing: `python -m unittest discover -s tests -v`.

---

## 3. Goals, non-goals and success measures

### Goals

- G1. A user can find any tracked article in under 10 seconds by keyword, brand or filter.
- G2. A user who follows an article gets a push within 15 minutes of the scan that detected the change.
- G3. Every article page shows a price and availability history chart.
- G4. Notifications are useful, not spam: a user never gets more than the caps in section 6.6.
- G5. The system costs at most USD 25 per month until it has real users, and can move to AWS without a rewrite.

### Non-goals

- Selling products or handling checkout. The app always links out to the brand's own store.
- Real-time (per-minute) stock tracking. See section 10 for why.

### Success measures (first 90 days after public release)

| Measure | Target |
| --- | --- |
| Scan success rate per brand per day | 95% or higher |
| Time from scan commit to push delivered | p95 under 15 minutes |
| Share of signed-in users with at least one follow | 60% or higher |
| Push open rate | 15% or higher |
| Day-30 retention | 20% or higher |
| Crash-free sessions | 99.5% or higher |
| Product page load (cached API) | p95 under 1.5 s on a mid-range Android phone on 4G |

---

## 4. Users and main journeys

- **Restock hunter.** Wants one article in one size. Opens the app from a push, taps "Buy on brand site".
- **Sale watcher.** Follows 5 to 15 brands, checks the feed for new discounts.
- **Price checker.** Arrives from a shared link, looks at the chart to see whether the "sale" price is real.

Journeys the app must support end to end:

1. Guest opens the app, searches "black kurta", filters to size M and in stock, sorts by biggest discount, opens an article, sees the chart.
2. Guest taps "Notify me", is asked to sign in with Google, comes back to the same article with the watch already saved.
3. User receives "Back in stock: Embroidered Lawn 3pc, size M, PKR 6,490", taps it, lands on the article, taps through to the brand site.
4. User opens the inbox, sees the last 30 days of alerts, mutes a noisy brand.

---

## 5. Architecture

### 5.1 Phase 1 (now, USD 0 to 25)

```
GitHub Actions (existing)                Supabase                         Clients
---------------------------             ---------------------            ---------------------
brands.yml: scan per brand   -->        Postgres                  <--    Expo app (Android, iOS)
  commit state.json to                    catalog tables                 Next.js site (phase 2)
  monitor-state branch                    history tables
        |                                 user tables (RLS)
        v                               Auth (Google, email)
ingest.yml (new):            -->        PostgREST + SQL RPCs
  read new commits on                   Edge Functions (optional)
  monitor-state, upsert,
  write events, send pushes  -->  Expo Push Service --> FCM / APNs --> devices
```

Principles:

- **The `monitor-state` branch stays the source of truth for scans.** The database is derived from it and can be rebuilt from it at any time.
- **Scanning and ingesting are separate.** A database outage must never block or corrupt a scan baseline. A scan failure must never produce events.
- **One ingest code path** serves both the historical backfill and the daily run.
- **Clients talk only to Supabase** (PostgREST and RPC) with the public anon key. The service-role key exists only in GitHub Actions secrets.

### 5.2 New code in this repository

| Path | Purpose |
| --- | --- |
| `pipeline/ingest.py` | Reads snapshots from `monitor-state` commits, upserts catalog rows, derives events |
| `pipeline/notify_push.py` | Matches events to watches and follows, writes inbox rows, sends pushes |
| `pipeline/normalize.py` | Maps brand `type`/`tags`/title to the shared category, gender and size vocabularies |
| `pipeline/tests/` | Unit tests with a local Postgres (Docker) or `pytest-postgresql` |
| `supabase/migrations/` | SQL migrations, RLS policies, RPC functions |
| `.github/workflows/ingest.yml` | Runs after `brands.yml` completes (`workflow_run`) and on manual dispatch |
| `.github/workflows/brands-hot.yml` | Phase 1b: hourly scan of hot brands only |

The mobile app lives in a **separate repository** (`stockwatch-app`), a pnpm monorepo:

```
apps/mobile      Expo app
apps/web         Next.js site (phase 2)
packages/api     typed Supabase client, generated DB types, query hooks
packages/ui      shared tokens (colors, spacing, type scale)
```

### 5.3 Ingest algorithm

For each brand:

1. Read `ingest_cursor.last_commit_sha` for the brand.
2. List commits on `monitor-state` that touched `brands/<slug>/state.json` after that commit, oldest first.
3. For each commit, load the snapshot and open one database transaction:
   - Insert a `scans` row keyed by `(brand_id, commit_sha)`. If it already exists, skip the commit.
   - Upsert products and variants.
   - Compare each variant's new price and availability with the current database row. When they differ, append to `price_points` / `stock_points` and insert a `product_events` row.
   - Products missing from the snapshot get `removed_at = checked_at` and a `removed` event. A product that reappears clears `removed_at`.
   - Update the cursor. Commit.
4. Events from commits older than 24 hours are marked `notifiable = false` (so the backfill never sends pushes).

Requirements:

- **ING-1** Idempotent: running the same commit twice changes nothing.
- **ING-2** A snapshot with `schema_version` other than 1, a non-PKR currency, a non-integer price, or fewer than 50% of the brand's live products present (a broken scrape or a re-keyed catalog) is rejected and logged in `scans.status = 'rejected'` with the reason, and an operator alert is raised. The cursor moves past the rejected commit so that the next good scan repairs the brand; a manual `--force` run accepts a catalog that really did shrink.
- **ING-3** The first snapshot of a brand creates products without `new_product` events.
- **ING-4** Ingest of one brand failing does not stop the other brands.
- **ING-5** Batched writes (`COPY` or multi-row upserts of 1,000 rows); a 2,000-product brand ingests in under 60 seconds.
- **ING-6** Descriptions are stored as plain text, HTML stripped, truncated to 2,000 characters.

### 5.4 Event kinds

`new_product`, `removed`, `back_in_stock`, `out_of_stock`, `price_drop`, `price_rise`, `sale_started` (compare-at price appears above price), `sale_ended`, `new_variant`.

Product-level events (`variant_id` null) drive feeds and product watches. `back_in_stock` at product level means "no variant was available, now at least one is". Price events follow `price_min`, the lowest price over all listed variants whether in stock or not, so a size selling out is never reported as a price change.

Variant-level events are written only for `back_in_stock` (that size flipped to available) and `new_variant`, and only for brands with size-level data. Per-size price history is in `price_points`; a size watch that wants price alerts is matched against the product-level price event plus that variant's `price_points`.

---

## 6. Functional requirements

### 6.1 Onboarding and auth

- **AUTH-1** The app is fully browsable as a guest: home, search, brand pages, article pages, charts.
- **AUTH-2** Following or watching requires sign-in. The pending action is completed automatically after sign-in.
- **AUTH-3** Sign-in methods: Google (native, via Supabase Auth) and email magic link. Email + password is allowed as a fallback.
- **AUTH-4** iOS build must add Sign in with Apple (App Store rule when third-party sign-in is offered).
- **AUTH-5** Account deletion inside the app and through a public web URL (Google Play rule). Deletion removes profile, follows, watches, devices and inbox.
- **AUTH-6** First-run onboarding: pick brands to follow (skippable), then the push permission prompt with a one-line reason. Never ask for push permission on first launch before showing value.

### 6.2 Home and feed

- **HOME-1** Tabs: Home, Search, Watchlist, Inbox, Profile.
- **HOME-2** Home shows: "Biggest price drops today", "Back in stock", "New arrivals", each a horizontal list, filtered to followed brands when the user has any, otherwise across all brands.
- **HOME-3** Every list is paginated and pull-to-refresh works.
- **HOME-4** Each card shows image, brand, title, current price, old price struck through, discount percent, in-stock state.

### 6.3 Search, filter, sort

- **SRCH-1** Keyword search over title, brand name, type, tags and SKU, tolerant of typos (Postgres full-text plus `pg_trgm`).
- **SRCH-2** Filters: brand (multi), category, gender, size, price range, in stock only, on sale only, minimum discount percent, new in the last 7/30 days.
- **SRCH-3** Sort: relevance, price low to high, price high to low, biggest discount, most recent price change, newest.
- **SRCH-4** Results return in under 400 ms p95 server time for the full catalog. Paging is limit/offset, capped at 50 rows per page and offset 2,000 (simpler than keyset and enough for a phone list); relevance is ranked over at most 3,000 matches.
- **SRCH-5** Recent searches are stored on the device only.
- **SRCH-6** Size filter is hidden for brands with product-level data only, and the article page states "Size availability not tracked for this brand".
- **SRCH-7** The `products` table reserves a nullable `embedding vector` column for phase 2 semantic search. Do not populate it in v1.

### 6.4 Brand page

- **BRAND-1** Logo, name, link to the store, last successful scan time, product count, follow button.
- **BRAND-2** Tabs: All, On sale, New, Back in stock. Same filters and sorts as search.
- **BRAND-3** A stale badge when the last successful scan is older than 48 hours.

### 6.5 Article page and chart

- **ART-1** Image gallery (swipe, pinch zoom), title, brand, current price, compare-at price, discount percent, availability, last checked time.
- **ART-2** Size selector that shows each variant's price and availability.
- **ART-3** "Buy on brand site" button opens the brand URL in the external browser, with affiliate/UTM parameters added from per-brand configuration.
- **ART-4** Watch button: whole article or a chosen size. Per-watch toggles: back in stock, price drop, any price change.
- **ART-5** Share button producing a universal link `https://<domain>/p/<brand-slug>/<handle>` that opens the app when installed.
- **ART-6** Stats row: lowest price ever, highest price ever, average over 90 days, number of price changes, days in stock out of the last 30.
- **ART-7** Description (collapsed), tags, "More from this brand".

Chart requirements:

- **CHART-1** Step line chart of price over time (prices change in steps, so no smoothing or interpolation).
- **CHART-2** Ranges: 1W, 1M, 3M, 6M, 1Y, All.
- **CHART-3** Press-and-drag crosshair with a tooltip showing date, price and in-stock state, with haptic tick.
- **CHART-4** Out-of-stock periods drawn as a shaded band behind the line.
- **CHART-5** Compare-at price as a second, dashed, lower-contrast line when it exists.
- **CHART-6** Lowest and highest points labelled. Y axis in PKR with thousands separators.
- **CHART-7** When a size is selected, the chart shows that variant; otherwise the lowest price over all listed variants.
- **CHART-8** Fewer than two data points shows "Tracking since <date>" instead of an empty chart.
- **CHART-9** Renders at 60 fps with 2,000 points on a mid-range Android phone.

### 6.6 Notifications

- **NOTIF-1** Triggers in v1:
  - Watched article or size: `back_in_stock`, `price_drop`, and `price_rise` if the user enabled "any price change".
  - Followed brand: one digest push per brand per day at most ("Khaadi: 42 new arrivals, 18 price drops"), opening a filtered list.
- **NOTIF-2** Each push deep-links to the article or the filtered list.
- **NOTIF-3** Every notification is also stored in the in-app inbox for 90 days, with read/unread state and an unread badge on the tab.
- **NOTIF-4** Caps per user: at most 10 item pushes per day, the rest are batched into one "and N more" push. At most 1 digest per followed brand per day.
- **NOTIF-5** Quiet hours, default 23:00 to 08:00 Asia/Karachi, user-editable. Pushes held during quiet hours are sent as one summary at the end.
- **NOTIF-6** Settings: global on/off, per-type toggles, per-brand mute.
- **NOTIF-7** Exactly-once: a unique key on `(user_id, event_id)` prevents duplicates on retries.
- **NOTIF-8** Price changes smaller than 1% or PKR 50 do not notify.
- **NOTIF-9** A `back_in_stock` followed by `out_of_stock` in the same ingest run does not notify.
- **NOTIF-10** Push tokens that the push service reports as invalid are deleted.
- **NOTIF-11** Push is sent through the Expo Push Service (free, forwards to FCM and APNs). Delivery receipts are checked in the next ingest run.

### 6.7 Watchlist and profile

- **WATCH-1** Watchlist tab: watched articles with current price, change since the watch began, and stock state; followed brands in a second segment.
- **WATCH-2** Swipe to remove; undo for 5 seconds.
- **PROF-1** Profile: account, theme (system, light, dark), notification settings, language (English only in v1, the setting exists), privacy policy, terms, delete account, contact/takedown email.

### 6.8 Operator needs

- **OPS-1** A `brand_health` SQL view: last scan, last success, product count, change count, consecutive failures.
- **OPS-2** An operator alert (email through the existing Resend key, or a Telegram/Discord webhook) when a brand fails 3 days in a row, when ingest fails, or when push error rate exceeds 5%.
- **OPS-3** Brands are added, hidden or re-tiered by editing a `brands` row; no app release needed.

---

## 7. Data model (Postgres)

All timestamps are `timestamptz` in UTC. All money is `bigint` minor units in PKR.

### Catalog

```sql
brands (
  id smallint primary key generated always as identity,
  slug text unique not null, name text not null,
  origin_url text not null, logo_url text,
  strategy text not null,
  granularity text not null check (granularity in ('variant','product')),
  scan_tier text not null default 'daily' check (scan_tier in ('hot','daily','paused')),
  affiliate_template text,
  is_visible boolean not null default true,
  product_count int not null default 0,
  last_scan_at timestamptz, last_success_at timestamptz
)

products (
  id bigint primary key generated always as identity,
  brand_id smallint not null references brands,
  external_id text not null,
  title text not null, handle text, url text not null,
  vendor text, raw_type text, description text,
  tags text[] not null default '{}', images text[] not null default '{}',
  options jsonb,
  category text, gender text,
  available boolean not null,
  price_min bigint, price_max bigint, compare_at_max bigint,
  discount_pct smallint,
  last_price_change_at timestamptz, last_restock_at timestamptz,
  first_seen_at timestamptz not null,
  removed_at timestamptz,          -- no last_seen_at: updating it would rewrite every row daily
  search tsvector,
  embedding vector(1024),            -- phase 2, null in v1
  unique (brand_id, external_id)
)

variants (
  id bigint primary key generated always as identity,
  product_id bigint not null references products on delete cascade,
  external_id text not null,
  title text, options text[], size_norm text, sku text,
  available boolean not null,
  price bigint not null, compare_at_price bigint,
  first_seen_at timestamptz not null, removed_at timestamptz,
  unique (product_id, external_id)
)
```

### History (append only, written only when a value changes)

The first change of a variant also writes the value it had since `first_seen_at`. A variant with no points has never changed: its chart is a flat line from `first_seen_at` at the current price.

```sql
price_points (variant_id bigint, observed_at timestamptz, price bigint, compare_at_price bigint,
              primary key (variant_id, observed_at))
stock_points (variant_id bigint, observed_at timestamptz, available boolean,
              primary key (variant_id, observed_at))

product_events (
  id bigint primary key generated always as identity,
  brand_id smallint not null, product_id bigint not null, variant_id bigint,
  kind text not null, old_value jsonb, new_value jsonb,
  observed_at timestamptz not null, scan_id bigint not null,
  notifiable boolean not null default true
)

scans (
  id bigint primary key generated always as identity,
  brand_id smallint not null, commit_sha text not null, checked_at timestamptz not null,
  product_count int, change_count int, status text not null, error text,
  unique (brand_id, commit_sha)
)
ingest_cursor (brand_id smallint primary key, last_commit_sha text not null)
```

### Users

```sql
profiles (id uuid primary key references auth.users on delete cascade,
          display_name text, quiet_start time, quiet_end time,
          timezone text default 'Asia/Karachi', prefs jsonb not null default '{}')
brand_follows (user_id uuid, brand_id smallint, muted boolean default false, created_at timestamptz,
               primary key (user_id, brand_id))
watches (id bigint primary key generated always as identity,
         user_id uuid not null, product_id bigint not null, variant_id bigint,
         on_restock boolean default true, on_price_drop boolean default true, on_any_price boolean default false,
         price_at_watch bigint, created_at timestamptz,
         unique (user_id, product_id, variant_id))
devices (id bigint primary key generated always as identity, user_id uuid not null,
         push_token text unique not null, platform text, app_version text, last_seen_at timestamptz)
notifications (id bigint primary key generated always as identity, user_id uuid not null,
               event_id bigint, kind text, title text, body text, deep_link text,
               created_at timestamptz, sent_at timestamptz, read_at timestamptz, status text,
               unique (user_id, event_id))
```

### Indexes and rules

- `products`: GIN on `search`, GIN `gin_trgm_ops` on `title`, btree on `(brand_id, removed_at)`, `(discount_pct desc)`, `(last_price_change_at desc)`, `(first_seen_at desc)`, `(category, gender)`.
- `variants`: `(product_id)`, `(size_norm) where available`.
- `product_events`: `(observed_at desc)`, `(product_id, observed_at desc)`, `(kind, observed_at desc)`.
- `watches`: `(product_id)`, `(variant_id)`.
- Row-level security: catalog and history tables are read-only for `anon` and `authenticated`; user tables allow access only where `user_id = auth.uid()`; `devices` and `notifications` writes from the pipeline use the service role.
- Search, feed and chart data are exposed as SQL RPC functions (`search_products`, `home_feed`, `product_detail`, `price_series`) so clients never build ad hoc queries and the same functions serve the website.
- `price_series(product_id, variant_id, range)` returns at most 500 points, downsampled server-side for long ranges.

### Size and storage plan

Measured: the full catalog is 1.31 GB (about 2.3 KB per product and 260 bytes per variant, indexes included). History is small because rows are written only on change: five days of scans, including the end of the 11.11 sales, added 53 MB.

The full catalog therefore does **not** fit in Supabase's free 500 MB database. Two workable setups:

- **Free tier, subset of brands (chosen).** Only the brands the owner lists under `include` in `pipeline/ingest_brands.json` are loaded; the budget is about 100,000 products (400 MB). Per-brand sizes are in `DEV_NOTES.md`.
- **Pro plan, USD 25/month, everything.** 8 GB of database included, which leaves room for more than a year of history at the measured rate.

A full backfill of all 206 commits takes about 9.5 minutes against a local database; a daily run re-reads every snapshot (1.2 GB of JSON) and will be dominated by upload time to the hosted database.

---

## 8. Mobile app specification

### 8.1 Stack

| Concern | Choice |
| --- | --- |
| Framework | Expo (latest stable SDK), React Native new architecture, TypeScript strict |
| Navigation | Expo Router (file-based, gives deep links and later web routes) |
| Server state | TanStack Query with persisted cache |
| Local state | Zustand; MMKV for storage |
| Backend client | `@supabase/supabase-js`, types generated with `supabase gen types` |
| Styling | NativeWind (Tailwind tokens shared with the phase 2 site) |
| Lists | FlashList |
| Images | `expo-image` with disk cache and blurhash/placeholder color |
| Charts | `victory-native` (Skia based) with Reanimated and Gesture Handler |
| Push | `expo-notifications` with FCM credentials |
| Auth | Supabase Auth, native Google sign-in, `expo-secure-store` for the session |
| i18n | `i18next` + `expo-localization`; no hard-coded strings in components |
| Validation | Zod at the API boundary |
| Errors | Sentry |
| Product analytics | PostHog |
| Tests | Jest + React Native Testing Library; Maestro for end-to-end flows |
| Build and release | EAS Build, EAS Submit, EAS Update for over-the-air JS fixes |

For the phase 2 website, use TradingView's open-source Lightweight Charts library (Apache 2.0, requires a TradingView attribution link) since it is a web canvas library.

### 8.2 Design direction

- Minimal, data-first, similar in feel to a trading app: neutral surfaces, one accent color, green for price drops and in stock, red for price rises and out of stock, never color alone (always an arrow or label too).
- Dark theme is the reference design; light theme has equal polish.
- Type: one family (Inter or the system font), tabular numerals for all prices.
- 4-point spacing grid, 44-point minimum touch targets, WCAG AA contrast.
- Skeleton loaders, not spinners. Empty states with one action. Offline banner with cached content still browsable.
- Layout tested from 320 dp wide phones to 10-inch tablets (two-column grid becomes four).
- All layout uses logical `start`/`end` properties so right-to-left works later.

### 8.3 Performance budgets

- Cold start to interactive under 2.5 s on a mid-range Android phone (for example a 4 GB RAM device).
- Android app bundle under 30 MB.
- Lists scroll at 60 fps; images requested at display size where the CDN supports size parameters (Shopify CDN URLs accept a `width` parameter).

### 8.4 Tools and skills for coding agents

- Before writing code, fetch current documentation for Expo, Supabase and victory-native (for example through a docs MCP server such as Context7); do not rely on memory for SDK versions.
- Supabase MCP server or Supabase CLI for migrations, type generation and RLS tests.
- Expo publishes agent skills and an MCP server for Expo projects; install them if available in the agent's environment.
- A frontend/UI design skill for the design system and screens, and a data-visualization skill for the chart.
- Maestro for scripted end-to-end runs on an Android emulator; agents must attach screenshots of each screen in light and dark themes to their pull requests.
- Every pull request runs typecheck, lint, unit tests and, for the pipeline, the Python unit tests.

---

## 9. Security, privacy and store compliance

- **SEC-1** The Supabase service-role key, Expo access token and proxy credentials live only in GitHub Actions secrets. The app ships only the anon key.
- **SEC-2** RLS is enabled on every table, with automated tests proving user A cannot read or write user B's rows.
- **SEC-3** RPC functions are `security invoker` unless there is a written reason; inputs are validated and page sizes capped at 50.
- **SEC-4** Rate limiting on search and auth endpoints (Supabase built-in limits plus per-IP limits; add Cloudflare in front when the website ships).
- **SEC-5** Personal data collected: email, display name, push token, follows and watches. Nothing else. No location, contacts or advertising ID in v1.
- **SEC-6** Privacy policy and terms hosted on a public URL; Google Play Data Safety form filled to match SEC-5; in-app and web account deletion (AUTH-5).
- **SEC-7** Outbound brand links open in the external browser; no WebView with injected scripts.
- **SEC-8** All product text is treated as untrusted and rendered as plain text.
- **SEC-9** Dependency audit and secret scanning in CI.

### Legal and platform risks the owner must accept or resolve

1. **Brand content.** The app shows brand names, logos and product photos it does not own. Mitigations: hotlink images from the brand CDN rather than rehosting, always link to the brand's page, show a "not affiliated with the listed brands" notice, publish a takedown contact and honor requests within 48 hours, and make any brand hideable instantly (OPS-3). This lowers risk but does not remove it; Google Play can also remove apps after an intellectual-property complaint. A short consultation with a lawyer before public launch is recommended.
2. **Scraping.** Only public pages are read. Respect `robots.txt` where it disallows the paths used, keep request rates low, and identify the bot with a contact URL where that does not get it blocked.
3. **Hotlinked images can break** when a brand changes its CDN. Phase 2 can add an image proxy/cache, which raises the content-rights question above.

---

## 10. Scan frequency: what is practical

### 10.1 Is scanning every brand every minute practical?

No, and it would not help users much.

- Volume: about 90 brands × 1,440 minutes is roughly 130,000 scans a day, or about 3.9 million a month. A full catalog scan is several paged requests, so that is on the order of 30 million requests and several terabytes of download a month.
- Blocking: one IP gets banned by Shopify for minutes after a short burst. Every-minute scanning needs a pool of rotating proxies. Some brands already block datacenter IPs, so part of the pool must be residential, which is billed per gigabyte (typically USD 3 to 8 per GB).
- Cost: roughly USD 600 or more for Lambda compute alone, plus proxies. With datacenter proxies only, a realistic total is USD 1,000 to 1,500 a month; with residential proxies for the traffic volume above it reaches five figures.
- Risk: that request rate against small stores is the kind of load that gets a scraper blocked permanently or draws complaints.
- Benefit: most catalogs change a few times a day, not every minute.

### 10.2 What to do instead

| Step | What | When |
| --- | --- | --- |
| 1 | Daily scan of all brands (today) | Now |
| 2 | **Hot tier:** hourly scan of the 10 to 20 most-followed brands in a second workflow, through one small proxy | Phase 1b |
| 3 | **Watch-driven polling:** every 10 to 15 minutes, fetch only the products that have active watchers (`/products/<handle>.js` on Shopify, one small request each). This gives near-real-time restock alerts for exactly the items people care about, at a tiny fraction of the cost | Phase 3 |
| 4 | **Change detection before full scans:** read the product sitemap `lastmod` values or use conditional requests, and fetch only products that changed. Needs a per-platform test to confirm that stock changes update `lastmod` | Phase 3 |
| 5 | Full catalog every 15 minutes for hot brands only | Only if users ask for it |

Limits of GitHub Actions to keep in mind: scheduled runs can start several minutes late and are skipped under load; scheduled workflows in a public repository are disabled after 60 days without repository activity; private repositories get 2,000 free minutes a month on the free plan, which the current multi-hour daily run would exceed (public repositories are free). Jobs run from datacenter IPs that some brands block.

### 10.3 AWS cost by stage (estimates)

Region `ap-south-1` (Mumbai) is the closest to Pakistan. Lambda should run outside a VPC to avoid NAT gateway charges (about USD 32 a month plus USD 0.045 per GB).

| Stage | Setup | Estimated monthly cost |
| --- | --- | --- |
| A. Now | GitHub Actions + Supabase free/Pro + Expo push + Sentry/PostHog free tiers | USD 0 to 25 |
| B. Hot hourly, rest daily, on AWS | EventBridge Scheduler → SQS → Lambda per brand (about 550 scans/day, inside or near the Lambda free tier); S3 for snapshots; Supabase Pro or RDS `db.t4g.micro`; small datacenter proxy plan; CloudWatch | USD 40 to 80 |
| C. All brands every 15 minutes | About 8,700 scans/day; Lambda about USD 30 to 50; proxy pool USD 50 to 150; RDS `db.t4g.small`/`medium` or Aurora Serverless v2 USD 30 to 90; logs and transfer USD 10 to 20 | USD 150 to 300 |
| D. All brands every minute | See 10.1 | USD 1,000 to 1,500+ (not recommended) |
| Watch-driven polling added to B | A few thousand small requests per cycle | Add USD 5 to 30 |

User-facing scale (independent of scan frequency):

| Monthly active users | What changes | Added cost |
| --- | --- | --- |
| Up to 5,000 | Nothing | USD 0 |
| 5,000 to 50,000 | Supabase Pro, cache RPC responses at the CDN edge, paid Sentry tier | USD 25 to 80 |
| 50,000 to 500,000 | Larger database instance, read replica, dedicated search engine (Typesense or OpenSearch), image proxy on CloudFront | USD 300 to 1,200 |

One-time and yearly: Google Play developer account USD 25 once; Apple Developer Program USD 99 a year; domain about USD 10 to 15 a year.

### 10.4 Target AWS architecture (phase 3, when stage A is outgrown)

- EventBridge Scheduler issues one message per brand per tier into SQS; a Lambda (container image with the existing Python code) scans one brand per invocation, with a dead-letter queue and per-brand concurrency of 1.
- Snapshots go to S3 (versioned bucket) instead of a git branch; an S3 event triggers the ingest Lambda. The ingest code is the same module, with a storage adapter (`GitStateStore`, `S3StateStore`).
- Postgres on RDS or Aurora Serverless v2, moved from Supabase with `pg_dump`/`pg_restore`. Supabase Auth can stay, or move to Cognito later; keeping Supabase for auth and database is also a valid end state.
- Push fan-out through SQS in batches of 100 to the Expo Push Service.
- CloudWatch structured JSON logs and alarms; Sentry stays for application errors.
- Infrastructure defined in code (AWS CDK or Terraform).

---

## 11. Database, logging and monitoring choices

| Need | Phase 1 choice | Why | Later |
| --- | --- | --- | --- |
| Main database | Postgres (Supabase) | Relational filters and sorts, full-text search, time-series by change, vector search later, all in one system | RDS / Aurora |
| Raw snapshots | `monitor-state` git branch (unchanged) | Already works; free; gives replay and backfill | S3 versioned bucket |
| Price history | Plain append-only tables | Change-only rows stay small | Monthly partitions, or TimescaleDB, past roughly 100 million rows |
| Search | Postgres `tsvector` + `pg_trgm` | No extra service | pgvector for semantic search; Typesense/OpenSearch if p95 exceeds target |
| Cache | TanStack Query on device; HTTP cache headers on RPC | Free | CDN edge cache, Redis only if measured need |
| Pipeline log | `scans` table + GitHub Actions logs | Queryable health history | CloudWatch Logs with JSON |
| App errors | Sentry (free tier) | Crash and JS error grouping, release health | Paid tier |
| Product analytics | PostHog (free tier) | Funnels, retention, feature flags | Same |
| Uptime and heartbeat | A free heartbeat monitor pinged at the end of ingest (for example healthchecks.io) | Alerts when the cron silently stops | CloudWatch alarms |

MongoDB and Firestore were considered and rejected: the core queries are relational filters, sorts and time ranges, which Postgres handles more directly.

---

## 12. Fault tolerance and quality

- **FT-1** Scan failure for a brand: baseline untouched, no ingest, no events, brand shows last good data with a stale badge after 48 hours.
- **FT-2** Database unavailable: scans still commit to `monitor-state`; the next ingest run catches up from the cursor.
- **FT-3** Ingest crashes mid-brand: the transaction rolls back; the rerun resumes from the cursor.
- **FT-4** Push service error: notification rows stay `pending` and are retried on the next run for up to 24 hours, then marked `expired`.
- **FT-5** A brand site returns a broken catalog (for example half the products missing): rejected by ING-2, so no mass "removed" or "out of stock" events reach users.
- **FT-6** App offline: cached screens remain readable; mutations queue and replay.
- **FT-7** Nightly automatic Supabase backup (Pro plan) plus the ability to rebuild catalog and history from `monitor-state`. User tables are the only data that cannot be rebuilt, so a weekly `pg_dump` of user tables to private storage is required while on the free tier.

Testing requirements:

- Pipeline: unit tests for event derivation (every event kind, first-scan rule, idempotency, rejection rule, removed and reappearing products), run against a real Postgres in CI.
- Notification matching: tests for caps, quiet hours, dedupe, thresholds, mute.
- RLS: tests per table.
- App: component tests for price formatting, chart data shaping, filters; Maestro flows for the four journeys in section 4.
- Load: `search_products` and `home_feed` tested with the full catalog and 50 concurrent users.

---

## 13. Delivery plan

Each milestone ends with a demo and the listed acceptance checks.

### M0. Foundations (pipeline repo + new app repo)
- Supabase project, migrations for section 7, RLS policies, generated types.
- App monorepo scaffold, CI, lint, typecheck, Sentry, design tokens, light/dark themes.
- Accept: migrations apply from zero; RLS tests pass; empty app builds as an Android APK through EAS.

### M1. Ingest and backfill
- `pipeline/ingest.py`, `normalize.py`, `ingest.yml`, backfill run over the full `monitor-state` history.
- Report: real product, variant, event counts and database size per brand.
- Turn off the owner's email digests: add an opt-out to `brands/run.py` / `brands/mailer.py` (for example an environment variable `MONITOR_EMAIL=off` set in `brands.yml`) so a run with email off still advances the baseline. `monitor.py` stays unchanged, and with email on, the existing rule "state advances only after every email is accepted" and its test must still hold. Do this only after the ingest has run correctly for 3 days in a row, so changes are never lost in between.
- Measure the total GitHub Actions minutes one full daily run uses. While the repository is private the free plan allows 2,000 minutes a month, and every job is rounded up to a whole minute; if the daily run would exceed that, reduce it (for example scan in one job instead of one job per brand) or make the repository public first.
- Accept: ING-1 to ING-6 tests pass; rerunning the backfill inserts zero rows; database size projection written into this document; Actions minutes per run recorded here.

### M2. Browse and search
- Home, Search, Brand page, Article page without chart; all filters and sorts; guest mode.
- Accept: journeys 1 and the SRCH requirements; p95 search under 400 ms on the full catalog.

### M3. Chart
- `price_series` RPC, chart component with CHART-1 to CHART-9, stats row.
- Accept: chart verified against hand-checked history for 5 articles; 60 fps on the reference phone.

### M4. Accounts, follows, watches
- Google and email sign-in, pending-action resume, watchlist, brand follows, account deletion.
- Accept: journey 2; AUTH requirements; RLS tests.

### M5. Notifications
- `notify_push.py`, device registration, inbox, settings, quiet hours, caps, deep links.
- Accept: NOTIF requirements; end-to-end test where a synthetic snapshot commit produces exactly one push on a test device within 15 minutes.

### M6. Operations (hot tier deferred)
- `brand_health` view, operator alerts, heartbeat.
- Deferred until the owner approves a proxy budget: `brands-hot.yml` hourly for hot brands (through `MONITOR_PROXY`), with the check "a hot brand's change reaches a device within 90 minutes".
- Accept: a forced failure raises an operator alert.

### M6b. Private test build
- EAS build of an installable Android APK (internal distribution) pointed at the real database, installed on the owner's phone. Over-the-air updates through EAS Update.
- Accept: the owner completes all four journeys in section 4 on their own phone and uses the app for at least one week; issues found are fixed before any store work begins.

### M7. Release (on hold until the owner asks for it)
- Store listing, screenshots, privacy policy, Data Safety form, closed testing track (Google requires new personal developer accounts to run a closed test with at least 12 testers for 14 days before production access), then production.
- Accept: crash-free sessions 99.5% in closed test; all four journeys pass on 3 physical devices.

### Phase 2
- Next.js website on Vercel or Cloudflare with server-rendered brand and article pages, `Product` and `Offer` structured data, sitemaps split per brand, canonical URLs, Open Graph images with the price chart, universal links into the app.
- Semantic search: embeddings for title + type + tags + short description in `pgvector`, hybrid ranking with keyword results. A one-time embedding of a few hundred thousand short texts costs a few dollars; after that only new or changed products are embedded.
- iOS release (Sign in with Apple, APNs key, App Store review).
- Target-price alerts and saved-search alerts.
- Variant-level scraping for the product-level brands.
- Optional weekly email digest to users through Resend.

### Phase 3
- AWS migration (section 10.4), watch-driven polling, change detection, 15-minute hot tier.

---

## 14. Future scope (practical ideas, not committed)

- "Is this sale real?" badge comparing the current price with the 90-day median and lowest price.
- Sale calendar: predicted sale periods per brand from past patterns (needs about a year of history).
- Similar articles across brands, and cheaper-alternative suggestions (uses the phase 2 embeddings).
- Search by photo.
- Home-screen widget for watched articles.
- Urdu interface and Roman-Urdu search synonyms ("kurta", "kameez", "jora").
- WhatsApp alerts through the WhatsApp Business API (paid per message, needs Meta business verification).
- Browser extension that shows the price history on the brand's own product page.
- Affiliate partnerships and sponsored brand placement, clearly labelled.
- Premium tier: faster alerts for watched items, unlimited watches, export.
- Anonymous aggregate insights for brands (most-watched articles, restock demand).
- More categories beyond fashion (electronics, cosmetics) by adding scraper strategies.

---

## 15. Build status

| Milestone | Status (2026-11-16) |
| --- | --- |
| M0 database | Done: `supabase/migrations/` (catalog, history, user tables, RLS, `brand_health`), `pipeline/migrate.py`. Not yet applied to a hosted database because no Supabase project exists |
| M0 app scaffold | Not started (separate repository) |
| M1 ingest and backfill | Code done and tested: `pipeline/ingest.py`, `pipeline/normalize.py`, 54 tests against a real Postgres (ingest rules, git backfill, RLS, API), `ingest.yml`, `pipeline-tests.yml`. Full backfill verified locally: 205 scans loaded, 1 rejected, a second run wrote zero rows |
| M1 remaining | Owner picks brands (`pipeline/ingest_brands.json`); add the `DATABASE_URL` secret; merge to `main`; first hosted run; turn off owner emails after 3 good days; measure GitHub Actions minutes |
| M2/M3 database API | Done: `search_products`, `home_feed`, `product_detail`, `price_series` (`supabase/migrations/20261116000003_api.sql`). On the full 380,000-product catalog locally, 16 typical calls each took under 160 ms (single warm runs, not a load test) |
| App screens (M2 to M4), push notifications (M5) | Not started |

Normalization coverage on the real catalog: 81% of variants in size-level brands get a normalized size; 74% of products get a gender; 6% of products fall in category `other`. The rules are a first version and have not been checked for accuracy by hand.

---

## 16. Open questions for the owner

None of these block the private test build. All must be settled before M7 (store release).

1. **App name, package ID and domain.** Placeholders are in use. The package ID is the app's permanent unique identifier on Google Play, written like a reversed web address (for example `pk.yourname.stockwatch`); users never see it, but it cannot be changed after the first Play Store upload. Choose the name first, then the ID follows from it.
2. **Hot-tier brands and proxy budget.** Deferred. Decide once there is real follow data.
3. **Category list.** Each brand names its product types differently ("Kurta", "KURTI", "2 Piece", or nothing). To make one filter work across all brands, the pipeline maps them to one shared list. As built (`pipeline/normalize.py`), there are two separate fields: `gender` (women, men, kids, or unknown) and `category` (unstitched, eastern, western, formal, footwear, bags-accessories, fragrance-beauty, home, other). The rules are keyword-based; changing them re-labels products on the next ingest.
4. **Affiliate programs.** Unknown. Revisit after public launch.
5. **Legal review** of brand content use before public launch (section 9).
6. **Google Play developer account.** Needed only to publish on the Play Store (one-time USD 25). Two types: *personal* (your own name and ID; Google then requires a closed test with 12 testers for 14 days before going public) or *organization* (needs a registered business). Not needed for the private test build.
